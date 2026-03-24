import os
import time
import requests
from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_pymongo import PyMongo
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev_key_778899_secure_random_string')

# --- CẤU HÌNH DATABASE ---
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)

# --- CẤU HÌNH API AI ---
# Sau khi bạn tạo API Engine (ở Bước 2), hãy dán link vào đây
AI_ENGINE_URL = "https://greendongnai-ai-engine.onrender.com" 

LABELS = ["Rác hữu cơ", "Rác nguy hại", "Rác tái chế", "Rác vô cơ"]
ACTIONS = [
    "Có thể dùng làm phân bón, bỏ vào thùng màu Xanh Lá.",
    "Cần xử lý riêng, hãy mang đến điểm thu gom rác độc hại.",
    "Hãy tráng sạch và bỏ vào thùng màu Xanh Dương!",
    "Bỏ vào thùng rác còn lại để đem đi chôn lấp."
]

def get_stats_data():
    try:
        stats = mongo.db.statistics.find_one({"id": "global_stats"})
        return stats if stats else {"total": 0}
    except:
        return {"total": 0}

# --- ROUTES ---

@app.route('/api/stats')
def api_stats():
    # Lấy dữ liệu từ MongoDB đã lưu khi quét ảnh
    stats = get_stats_data()
    # Nếu chưa có dữ liệu thì trả về mảng 0
    counts = stats.get('counts', [0, 0, 0, 0])
    
    return jsonify({
        "labels": ["Hữu cơ", "Nguy hại", "Tái chế", "Vô cơ"],
        "counts": counts
    })

@app.route('/')
def home():
    if 'user' not in session: 
        return redirect(url_for('landing'))
    stats = get_stats_data()
    return render_template('trang_chu.html', total_scans=stats.get('total', 0), username=session['user'])

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/phan-loai')
def phan_loai():
    if 'user' not in session: 
        return redirect(url_for('login'))
    return render_template('phan_loai.html')

@app.route('/nhan_dien_anh', methods=['GET', 'POST'])
def AI_image():
    if 'user' not in session: 
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('Vui lòng chọn ảnh!')
            return redirect(url_for('phan_loai'))
        
        try:
            # 1. Lưu ảnh tạm thời
            filename = secure_filename(f"img_{int(time.time())}.jpg")
            upload_folder = os.path.join(app.root_path, 'static', 'anh')
            if not os.path.exists(upload_folder): os.makedirs(upload_folder)
            upload_path = os.path.join(upload_folder, filename)
            file.save(upload_path)

            # 2. GỌI API ĐỂ XỬ LÝ AI
            with open(upload_path, 'rb') as f:
                response = requests.post(AI_ENGINE_URL, files={'file': f}, timeout=20)
            
            if response.status_code == 200:
                result = response.json()
                res_idx = result['result_index']
                conf = result['confidence']

                # 3. Cập nhật DB
                mongo.db.statistics.update_one(
                    {"id": "global_stats"},
                    {"$inc": {f"counts.{res_idx}": 1, "total": 1}},
                    upsert=True
                )
                
                return render_template('nhan_dien_anh.html', 
                                     prediction=LABELS[res_idx], 
                                     confidence=f"{conf*100:.1f}%",
                                     action=ACTIONS[res_idx],
                                     user_image=filename)
            
            flash("API AI đang bận hoặc khởi động chậm. Thử lại sau 10 giây!")
            return redirect(url_for('phan_loai'))

        except Exception as e:
            print(f"Lỗi: {e}")
            flash("Không thể kết nối với AI Engine.")
            return redirect(url_for('phan_loai'))
            
    return render_template('nhan_dien_anh.html', prediction=None)

# --- GIỮ NGUYÊN LOGIN/SIGNUP ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username, email, password = request.form.get('username'), request.form.get('email'), request.form.get('password')
        if password != request.form.get('passwordconfirm'):
            flash("Mật khẩu không khớp!"); return redirect(url_for('signup'))
        
        if mongo.db.users.find_one({"username": username}):
            flash("Tài khoản đã tồn tại!"); return redirect(url_for('signup'))
            
        mongo.db.users.insert_one({"username": username, "email": email, "password": generate_password_hash(password)})
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not identity or not password:
            flash("Vui lòng nhập đầy đủ tài khoản và mật khẩu!")
            return render_template('login.html')
        # 2. Tìm người dùng trong Database (Email hoặc Username)
        user = mongo.db.users.find_one({
            "$or": [{"username": identity}, {"email": identity}]
        })
        # 3. Kiểm tra mật khẩu an toàn
        if user and 'password' in user:
            if check_password_hash(user['password'], password):
                session['user'] = user['username']
                return redirect(url_for('home')) 
        flash("Sai tài khoản hoặc mật khẩu!")     
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))