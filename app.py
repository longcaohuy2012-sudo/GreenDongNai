import os
import time
import numpy as np
from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from PIL import Image
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    from tensorflow.lite.python.interpreter import Interpreter as tflite # Dự phòng

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev_key_778899_secure_random_string')

# --- CẤU HÌNH DATABASE ---
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)

# --- CẤU HÌNH AI TFLITE ---
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'waste_model.tflite')
LABELS = ["Rác hữu cơ", "Rác nguy hại", "Rác tái chế", "Rác vô cơ"]
ACTIONS = [
    "Hãy tráng sạch và bỏ vào thùng màu Xanh Dương!",
    "Bỏ vào thùng rác còn lại để đem đi chôn lấp.",
    "Có thể dùng làm phân bón, bỏ vào thùng màu Xanh Lá.",
    "Cần xử lý riêng, hãy mang đến điểm thu gom rác độc hại."
]

def predict_trash(img_path):
    """Hàm xử lý ảnh và dự đoán bằng TFLite"""
    try:
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Tiền xử lý ảnh (Resize về 224x224 cho nhẹ RAM)
        img = Image.open(img_path).convert('RGB').resize((224, 224))
        img_array = np.array(img, dtype=np.float32) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        interpreter.set_tensor(input_details[0]['index'], img_array)
        interpreter.invoke()
        
        prediction = interpreter.get_tensor(output_details[0]['index'])
        result_index = np.argmax(prediction)
        confidence = float(np.max(prediction))
        
        return result_index, confidence
    except Exception as e:
        print(f"Lỗi AI: {e}")
        return None, 0

# --- HÀM BỔ TRỢ DATABASE ---
def get_stats_data():
    mongo.db.statistics.update_one(
        {"id": "global_stats"},
        {"$setOnInsert": {
            "labels": LABELS,
            "counts": [0, 0, 0, 0],
            "total": 0
        }},
        upsert=True
    )
    return mongo.db.statistics.find_one({"id": "global_stats"})

def update_stats(index):
    mongo.db.statistics.update_one(
        {"id": "global_stats"},
        {"$inc": {f"counts.{index}": 1, "total": 1}}
    )

# --- ROUTES ---

@app.route('/')
def home():
    if 'user' not in session: return redirect(url_for('landing'))
    stats = get_stats_data()
    return render_template('trang_chu.html', total_scans=stats['total'], username=session['user'])

@app.route('/phan-loai') # Đây là địa chỉ URL trên trình duyệt
def phan_loai():        # Tên hàm này phải khớp với chữ trong url_for
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('phan_loai.html')

@app.route('/nhan_dien_anh', methods=['GET', 'POST'])
def AI_image():
    # 1. Kiểm tra đăng nhập
    if 'user' not in session: 
        return redirect(url_for('login'))
    
    # 2. Xử lý khi người dùng GỬI ẢNH (POST)
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('Vui lòng chọn ảnh trước khi bấm nhận diện!')
            return redirect(url_for('phan_loai'))

        try:
            # Lưu ảnh vào folder static/ảnh (Khớp với cấu trúc của bạn)
            filename = secure_filename(f"user_{int(time.time())}_{file.filename}")
            upload_folder = os.path.join(app.root_path, 'static', 'ảnh')
            
            # Tự động tạo thư mục 'ảnh' nếu chưa có để tránh lỗi sập web
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
                
            upload_path = os.path.join(upload_folder, filename)
            file.save(upload_path)

            # 3. GỌI AI DỰ ĐOÁN
            result_index, confidence = predict_trash(upload_path)

            if result_index is not None:
                # Cập nhật số liệu vào MongoDB
                update_stats(result_index)
                
                # Trả kết quả về lại file nhan_dien_anh.html
                return render_template('nhan_dien_anh.html', 
                                     prediction=LABELS[result_index], 
                                     confidence=f"{confidence*100:.1f}%",
                                     action=ACTIONS[result_index],
                                     user_image=filename) # Gửi tên file để hiển thị lại ảnh
            
            flash("AI gặp sự cố khi phân tích. Hãy thử ảnh khác!")
            return redirect(url_for('phan_loai'))

        except Exception as e:
            print(f"Lỗi hệ thống: {e}")
            flash("Đã xảy ra lỗi trong quá trình xử lý.")
            return redirect(url_for('phan_loai'))

    # 4. Xử lý khi người dùng TRUY CẬP TRỰC TIẾP (GET)
    # Trả về trang trống hoặc trang hướng dẫn để tránh lỗi 405
    return render_template('nhan_dien_anh.html', prediction=None)

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
    app.run(host='0.0.0.0', port=port, debug=False)