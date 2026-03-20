import os
import time
import json
from flask import Flask, flash, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_FILE = os.path.join(BASE_DIR, 'users.json')

app = Flask(__name__)
app.secret_key = 'greendongnai_2026'

# 1. CẤU HÌNH ĐƯỜNG DẪN
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

USER_FILE = os.path.join(BASE_DIR, 'users.json')

# 2. CÁC HÀM BỔ TRỢ
def get_users():
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, 'w', encoding='utf-8') as f: 
            json.dump({}, f)
        return {}
    try:
        with open(USER_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        return {}

def save_users(users):
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# 3.ROUTES
@app.route('/api/stats')
def get_stats():
    # Giả sử bạn lấy dữ liệu từ file stats.json hoặc database
    data = {
        "labels": ["Rác tái chế", "Rác vô cơ", "Rác hữu cơ", "Rác nguy hại"],
        "counts": [1500, 1000, 667, 500],
        "total": 3667
    }
    return jsonify(data)

@app.route('/phan_loai')
def phan_loai():
    return "Trang hướng dẫn phân loại đang được xây dựng!"

@app.route('/landing', methods=['GET', 'POST'])
def landing():
    if request.method == 'POST':
        return redirect(url_for('login'))
    return render_template('landing.html')

@app.route('/')
def home():
    if 'user' not in session: 
        return redirect(url_for('landing'))
    return render_template('trang_chu.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        confirm = request.form.get('passwordconfirm')
        
        if not user or not password:
            flash("Vui lòng điền đầy đủ thông tin!")
            return redirect(url_for('signup'))

        users = get_users()
        if user in users:
            flash("Tên tài khoản này đã tồn tại!")
            return redirect(url_for('signup'))
            
        existing_emails = [info.get('email') for info in users.values()]
        if email in existing_emails:
            flash("Email này đã được sử dụng!")
            return redirect(url_for('signup'))

        if password != confirm:
            flash("Mật khẩu xác nhận không khớp!")
            return redirect(url_for('signup'))
            
        users[user] = {"email": email, "password": password}
        save_users(users)
        flash("Đăng ký thành công! Hãy đăng nhập.")
        return redirect(url_for('login'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('username', '').strip()
        password = request.form.get('password')
        users = get_users()
        
        target_user = None
        username_final = None

        if identity in users:
            target_user = users[identity]
            username_final = identity
        else:
            for u_name, u_info in users.items():
                if u_info.get('email') == identity:
                    target_user = u_info
                    username_final = u_name
                    break
        
        if target_user and target_user.get("password") == password:
            session['user'] = username_final
            return redirect(url_for('home'))
        
        flash("Tên đăng nhập/Email hoặc mật khẩu không đúng!")
        return redirect(url_for('login'))
        
    return render_template('login.html')

@app.route('/nhan_dien_anh', methods=['POST'])
def AI_image():
    if 'user' not in session: return redirect(url_for('login'))
    
    if 'file' not in request.files:
        flash('Không tìm thấy file ảnh!')
        return redirect(url_for('home'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Bạn chưa chọn ảnh.')
        return redirect(url_for('home'))

    if file:
        ext = file.filename.rsplit('.', 1)[-1].lower()
        filename = secure_filename(f"trash_{int(time.time())}.{ext}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        result = {
            "label": "Giấy vụn",
            "type": "Rác tái chế (nếu sạch)",
            "action": "Hãy bỏ vào thùng rác màu xanh dương nếu giấy không dính dầu mỡ nhé!"
        }
        return render_template('ket_qua.html', result=result, img_path=filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
#---chạy web giữa file---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)        
