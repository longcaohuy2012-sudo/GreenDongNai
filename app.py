import os
import time
import numpy as np
from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from PIL import Image

# SỬ DỤNG TENSORFLOW ĐẦY ĐỦ
import tensorflow as tf

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev_key_778899_secure_random_string')

# --- CẤU HÌNH DATABASE ---
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)

# --- CẤU HÌNH AI TENSORFLOW ---
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'waste_model.tflite')
LABELS = ["Rác hữu cơ", "Rác nguy hại", "Rác tái chế", "Rác vô cơ"]
ACTIONS = [
    "Có thể dùng làm phân bón, bỏ vào thùng màu Xanh Lá.", # Hữu cơ
    "Cần xử lý riêng, hãy mang đến điểm thu gom rác độc hại.", # Nguy hại
    "Hãy tráng sạch và bỏ vào thùng màu Xanh Dương!", # Tái chế
    "Bỏ vào thùng rác còn lại để đem đi chôn lấp." # Vô cơ
]

# --- KHỞI TẠO AN TOÀN VỚI TENSORFLOW ---
interpreter = None
try:
    if os.path.exists(MODEL_PATH):
        # TensorFlow full thường xử lý file tflite tốt hơn tflite-runtime trên Linux
        #interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
        interpreter.allocate_tensors()
        print("✅ TensorFlow đã tải model thành công!")
    else:
        print(f"❌ Không tìm thấy file model tại: {MODEL_PATH}")
except Exception as e:
    print(f"❌ Lỗi khởi tạo model: {str(e)}")
    interpreter = None

def predict_trash(img_path):
    if interpreter is None:
        return None, 0
    try:
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Tiền xử lý ảnh (224x224)
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
    try:
        stats = mongo.db.statistics.find_one({"id": "global_stats"})
        if not stats:
            mongo.db.statistics.insert_one({
                "id": "global_stats",
                "counts": [0, 0, 0, 0],
                "total": 0
            })
            return {"total": 0}
        return stats
    except:
        return {"total": 0}

# --- ROUTES ---

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
@app.route('/predict', methods=['POST']) # Thêm route này để dự phòng cho HTML cũ
def AI_image():
    if 'user' not in session: 
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('Vui lòng chọn ảnh trước khi bấm nhận diện!')
            return redirect(url_for('phan_loai'))
        try:
            filename = secure_filename(f"img_{int(time.time())}.jpg")
            upload_folder = os.path.join(app.root_path, 'static', 'anh')
            
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)    
            
            upload_path = os.path.join(upload_folder, filename)
            file.save(upload_path)
            
            result_index, confidence = predict_trash(upload_path)
            
            if result_index is not None:
                # Cập nhật database
                mongo.db.statistics.update_one(
                    {"id": "global_stats"},
                    {"$inc": {f"counts.{result_index}": 1, "total": 1}}
                )
                
                return render_template('nhan_dien_anh.html', 
                                     prediction=LABELS[result_index], 
                                     confidence=f"{confidence*100:.1f}%",
                                     action=ACTIONS[result_index],
                                     user_image=filename) 
            
            flash("AI gặp sự cố khi phân tích.")
            return redirect(url_for('phan_loai'))
        except Exception as e:
            print(f"Lỗi: {e}")
            flash("Đã xảy ra lỗi.")
            return redirect(url_for('phan_loai'))
            
    return render_template('nhan_dien_anh.html', prediction=None)

# --- (Các route signup, login, logout giữ nguyên như code của bạn) ---
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
        existing_user = mongo.db.users.find_one({
            "$or": [{"username": username}, {"email": email}]
        })
        if existing_user:
            flash("Tên đăng nhập hoặc Email đã tồn tại!")
            return redirect(url_for('signup'))
        if password != confirm:
            flash("Mật khẩu xác nhận không khớp!")
            return redirect(url_for('signup'))
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)