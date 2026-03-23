import os
import time
from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_pymongo import PyMongo
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

app = Flask(__name__)

# BẢO MẬT: Lấy Secret Key từ .env, nếu không có sẽ dùng chuỗi tạm an toàn
app.secret_key = os.getenv('SECRET_KEY', 'dev_key_778899_secure_random_string')

# --- CẤU HÌNH DATABASE (MONGODB) ---
# Đảm bảo MONGO_URI trong Render đã sửa thành: 
# mongodb+srv://longcaohuy2012_db_user:LONG10122012@green-dong-nai.dakgulr.mongodb.net/Green-Dong-Na?retryWrites=true&w=majority
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)

# --- CẤU HÌNH THƯ MỤC UPLOAD ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- HÀM BỔ TRỢ SỐ LIỆU (FIX LỖI NHÂN BẢN) ---
def get_stats_data():
    """Lấy số liệu thống kê bằng cơ chế Upsert (Cập nhật nếu có, tạo nếu chưa)"""
    # Sử dụng $setOnInsert để chỉ khởi tạo dữ liệu khi bản ghi chưa tồn tại
    mongo.db.statistics.update_one(
        {"id": "global_stats"},
        {"$setOnInsert": {
            "labels": ["Rác tái chế", "Rác vô cơ", "Rác hữu cơ", "Rác nguy hại"],
            "counts": [0, 0, 0, 0],
            "total": 0
        }},
        upsert=True
    )
    return mongo.db.statistics.find_one({"id": "global_stats"})

def update_stats(index):
    """Tăng số lượng rác theo loại dựa trên vị trí index (0-3)"""
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
    total = stats.get('total', 0) if stats else 0
    return render_template('trang_chu.html', 
                           total_scans=total, 
                           username=session['user'])

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/phan-loai')
def phan_loai():
    return render_template('phan_loai.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        confirm = request.form.get('passwordconfirm')

        if not username or not password or not email:
            flash("Vui lòng điền đầy đủ thông tin!")
            return redirect(url_for('signup'))

        # Kiểm tra trùng lặp
        existing_user = mongo.db.users.find_one({
            "$or": [{"username": username}, {"email": email}]
        })
        
        if existing_user:
            flash("Tên đăng nhập hoặc Email đã tồn tại!")
            return redirect(url_for('signup'))

        if password != confirm:
            flash("Mật khẩu xác nhận không khớp!")
            return redirect(url_for('signup'))

        # Lưu người dùng với mật khẩu đã băm (hashed)
        hashed_password = generate_password_hash(password)
        mongo.db.users.insert_one({
            "username": username,
            "email": email,
            "password": hashed_password,
            "created_at": time.time()
        })
        
        flash("Đăng ký thành công! Hãy đăng nhập.")
        return redirect(url_for('login'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('username', '').strip()
        password = request.form.get('password')

        user = mongo.db.users.find_one({
            "$or": [{"username": identity}, {"email": identity}]
        })

        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            return redirect(url_for('home'))
        
        flash("Sai tài khoản hoặc mật khẩu!")
        
    return render_template('login.html')

@app.route('/nhan_dien_anh', methods=['POST'])
def AI_image():
    if 'user' not in session: 
        return redirect(url_for('login'))
    
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Vui lòng chọn ảnh.')
        return redirect(url_for('home'))

    ext = file.filename.rsplit('.', 1)[-1].lower()
    filename = secure_filename(f"trash_{int(time.time())}.{ext}")
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    # Giả lập AI: Tự động cộng 1 vào Rác tái chế (index 0)
    update_stats(0) 

    result = {
        "label": "Chai nhựa PET",
        "type": "Rác tái chế",
        "action": "Hãy tráng sạch và bỏ vào thùng màu Xanh Dương!"
    }
    return render_template('ket_qua.html', result=result, img_path=filename)

@app.route('/api/stats')
def get_stats_api():
    """API cho biểu đồ lấy dữ liệu"""
    stats = get_stats_data()
    return jsonify({
        "labels": stats["labels"],
        "counts": stats["counts"],
        "total": stats["total"]
    })

# --- XÁC MINH GOOGLE SEARCH CONSOLE ---
# Thay 'google-code.html' bằng mã thực tế từ Google cung cấp
@app.route('/google5399e6fea12a6540.html')
def google_verify():
    return "google-site-verification: google5399e6fea12a6540.html"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)