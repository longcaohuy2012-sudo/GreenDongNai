import os
import time
import json
from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify # Thêm jsonify vào đây
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'greendongnai_2026'

# 1. CẤU HÌNH ĐƯỜNG DẪN
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
USER_FILE = os.path.join(BASE_DIR, 'users.json')
STATS_FILE = os.path.join(BASE_DIR, 'stats.json') # File lưu số liệu rác

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 2. CÁC HÀM BỔ TRỢ DỮ LIỆU
def get_users():
    if not os.path.exists(USER_FILE):
        save_users({})
        return {}
    try:
        with open(USER_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip() # Đọc và loại bỏ khoảng trắng
            if not content: # Nếu file rỗng tuếch
                return {}
            return json.loads(content)
    except Exception as e:
        print(f"Lỗi đọc file: {e}")
        return {}
def save_users(users):
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# --- HÀM XỬ LÝ SỐ LIỆU THỐNG KÊ ---
def get_stats_data():
    initial_stats = {
        "labels": ["Rác tái chế", "Rác vô cơ", "Rác hữu cơ", "Rác nguy hại"],
        "counts": [1500, 1000, 667, 500],
        "total": 3667
    }
    if not os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_stats, f, ensure_ascii=False, indent=4)
        return initial_stats
    
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content: return initial_stats
            return json.loads(content)
    except:
        return initial_stats
def update_stats(waste_type_index):
    data = get_stats_data()
    data['counts'][waste_type_index] += 1 # Tăng loại rác tương ứng
    data['total'] += 1 # Tăng tổng số
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)

# 3. ROUTES
@app.route('/')
def home():
    if 'user' not in session: 
        return redirect(url_for('landing'))
    stats = get_stats_data()
    # Truyền số total ra trang chủ để hiển thị
    return render_template('trang_chu.html', total_scans=stats['total'])

@app.route('/phan_loai')
def phan_loai():
    return render_template('phan_loai.html')

@app.route('/api/stats')
def get_stats():
    # Trả về dữ liệu thực từ file stats.json cho biểu đồ
    return jsonify(get_stats_data())
@app.route('/debug/users')
def debug_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    return "File không tồn tại!"
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
    
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Bạn chưa chọn ảnh.')
        return redirect(url_for('home'))

    # Lưu ảnh
    ext = file.filename.rsplit('.', 1)[-1].lower()
    filename = secure_filename(f"trash_{int(time.time())}.{ext}")
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    # Giả lập AI nhận diện được "Rác tái chế" (index 0 trong mảng counts)
    update_stats(0) 

    result = {
        "label": "Giấy vụn",
        "type": "Rác tái chế",
        "action": "Hãy bỏ vào thùng rác màu xanh dương nhé!"
    }
    return render_template('ket_qua.html', result=result, img_path=filename)

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)