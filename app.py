import os
import time
from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_pymongo import PyMongo
from dotenv import load_dotenv

# Load biến môi trường từ file .env (khi chạy ở máy)
load_dotenv()

app = Flask(__name__)
# Lấy Secret Key từ env, nếu không có thì dùng mặc định (để tránh lỗi)
app.secret_key = os.getenv('SECRET_KEY', 'Gree_Dong_Nai_2026_Cao_Huy_Long_Nguyen_Hoang_Long')

# --- CẤU HÌNH DATABASE (MONGODB) ---
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)

# --- CẤU HÌNH THƯ MỤC UPLOAD ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- HÀM BỔ TRỢ SỐ LIỆU (DATABASE VERSION) ---
def get_stats_data():
    """Lấy số liệu thống kê từ MongoDB"""
    stats = mongo.db.statistics.find_one({"id": "global_stats"})
    if not stats:
        # Khởi tạo nếu chưa có dữ liệu trong DB
        stats = {
            "id": "global_stats",
            "labels": ["Rác tái chế", "Rác vô cơ", "Rác hữu cơ", "Rác nguy hại"],
            "counts": [1500, 1000, 667, 500],
            "total": 3667
        }
        mongo.db.statistics.insert_one(stats)
    return stats

def update_stats(index):
    """Tăng số lượng rác theo loại"""
    mongo.db.statistics.update_one(
        {"id": "global_stats"},
        {"$inc": {f"counts.{index}": 1, "total": 1}}
    )

# --- CÁC ĐƯỜNG DẪN (ROUTES) ---

@app.route('/')
def home():
    if 'user' not in session: 
        return redirect(url_for('landing'))
    
    stats = get_stats_data()
    return render_template('trang_chu.html', 
                           total_scans=stats['total'], 
                           username=session['user'])

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        confirm = request.form.get('passwordconfirm')

        if not username or not password or not email:
            flash("Vui lòng điền đầy đủ tất cả các trường!")
            return redirect(url_for('signup'))

        # Kiểm tra trùng lặp trong Database
        existing_user = mongo.db.users.find_one({
            "$or": [{"username": username}, {"email": email}]
        })
        
        if existing_user:
            flash("Tên đăng nhập hoặc Email đã được sử dụng!")
            return redirect(url_for('signup'))

        if password != confirm:
            flash("Mật khẩu xác nhận không khớp!")
            return redirect(url_for('signup'))

        # Lưu người dùng mới với mật khẩu ĐÃ MÃ HÓA
        hashed_password = generate_password_hash(password)
        mongo.db.users.insert_one({
            "username": username,
            "email": email,
            "password": hashed_password,
            "created_at": time.time()
        })
        
        flash("Đăng ký thành công! Chào mừng bạn gia nhập cộng đồng Xanh.")
        return redirect(url_for('login'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('username', '').strip()
        password = request.form.get('password')

        # Tìm người dùng theo username hoặc email
        user = mongo.db.users.find_one({
            "$or": [{"username": identity}, {"email": identity}]
        })

        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            return redirect(url_for('home'))
        
        flash("Sai thông tin đăng nhập hoặc mật khẩu!")
        
    return render_template('login.html')

@app.route('/nhan_dien_anh', methods=['POST'])
def AI_image():
    if 'user' not in session: 
        return redirect(url_for('login'))
    
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Vui lòng chọn một tấm ảnh rác để nhận diện.')
        return redirect(url_for('home'))

    # Lưu file tạm thời
    ext = file.filename.rsplit('.', 1)[-1].lower()
    filename = secure_filename(f"trash_{int(time.time())}.{ext}")
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    # Giả lập AI: Ở đây mình mặc định là rác tái chế (index 0)
    # Long có thể thay phần này bằng code gọi Model AI thực tế sau này
    update_stats(0) 

    result = {
        "label": "Chai nhựa nhựa PET",
        "type": "Rác tái chế",
        "action": "Hãy tráng sạch và bỏ vào thùng Rác Tái Chế (Màu Xanh Dương)!"
    }
    return render_template('ket_qua.html', result=result, img_path=filename)

@app.route('/api/stats')
def get_stats():
    #API để JavaScript vẽ biểu đồ lấy dữ liệu
    stats = get_stats_data()
    return jsonify({
        "labels": stats["labels"],
        "counts": stats["counts"],
        "total": stats["total"]
    })

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)