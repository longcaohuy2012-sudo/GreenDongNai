import os
import time
import json
from flask import Flask, flash, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.secret_key = 'greendongnai_2026'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_FILE = os.path.join(BASE_DIR, 'users.json')
# --- HÀM BỔ TRỢ CẬP NHẬT ---
def get_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

# --- ROUTES ---

@app.route('/landing', methods = ['GET', 'POST'])
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
        
        users = get_users()

        # 1. Kiểm tra trùng Username
        if user in users:
            flash("Tên tài khoản này đã tồn tại!")
            return redirect(url_for('signup'))
            
        # 2. Kiểm tra trùng Email (1 email chỉ 1 tài khoản) [HÀNH ĐỘNG MỚI]
        existing_emails = [info.get('email') for info in users.values()]
        if email in existing_emails:
            flash("Email này đã được sử dụng cho tài khoản khác!")
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
        identity = request.form.get('username', '').strip() # Có thể là User hoặc Email
        password = request.form.get('password')
        users = get_users()
        
        target_user = None

        # Logic Đăng nhập 2 in 1
        if identity in users:
            # Nếu identity là Username trực tiếp
            target_user = users[identity]
            username_final = identity
        else:
            # Nếu identity không phải username, kiểm tra xem nó có phải Email ko
            for u_name, u_info in users.items():
                if u_info.get('email') == identity:
                    target_user = u_info
                    username_final = u_name
                    break
        
        if target_user and target_user.get("password") == password:
            session['user'] = username_final
            return redirect(url_for('home')) # home là trang chính của app
        
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
        # Lưu file
        ext = file.filename.rsplit('.', 1)[-1].lower()
        filename = secure_filename(f"trash_{int(time.time())}.{ext}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # GIẢ LẬP KẾT QUẢ AI (Chỗ này để Long lắp mô hình sau)
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)