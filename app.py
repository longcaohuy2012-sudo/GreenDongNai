import os
import time
import requests
from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from datetime import timedelta
import base64

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev_key_778899_secure_random_string')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
# Duy trì đăng nhập trong 7 ngày
app.permanent_session_lifetime = timedelta(days=7)

# --- CẤU HÌNH DATABASE ---
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)

# --- CẤU HÌNH API AI ---
AI_ENGINE_URL = "https://greendongnai-ai-engine.onrender.com/predict" 

LABELS = ["Rác hữu cơ", "Rác nguy hại", "Rác tái chế", "Rác vô cơ"]
ACTIONS = [
    "Có thể dùng làm phân bón, bỏ vào thùng màu Xanh Lá.",
    "Hãy mang rác đến các điểm thu gom rác nguy hại",
    "Hãy tráng sạch và bỏ vào thùng màu Xanh Dương!",
    "Bỏ vào thùng rác còn lại để đem đi chôn lấp."
]

def get_stats_data():
    try:
        stats = mongo.db.statistics.find_one({"id": "global_stats"})
        return stats if stats else {"total": 0, "counts": [0, 0, 0, 0]}
    except:
        return {"total": 0, "counts": [0, 0, 0, 0]}

# --- ROUTES ---

@app.route('/api/stats')
def api_stats():
    stats = get_stats_data()
    return jsonify({
        "labels": ["Hữu cơ", "Nguy hại", "Tái chế", "Vô cơ"],
        "counts": stats.get('counts', [0, 0, 0, 0])
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
            filename = secure_filename(f"img_{int(time.time())}.jpg")
            upload_folder = os.path.join(app.root_path, 'static', 'anh')
            if not os.path.exists(upload_folder): os.makedirs(upload_folder)
            upload_path = os.path.join(upload_folder, filename)
            file.save(upload_path)

            with open(upload_path, 'rb') as f:
                # Gửi ảnh sang Engine (Timeout 25s)
                response = requests.post(AI_ENGINE_URL, files={'file': f}, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                res_idx = result.get('result_index', 0)
                #Engine không trả về mức độ chắc chắn (confidence), mặc định 90%
                conf = result.get('confidence', 0.9) 

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
            
            flash("AI Engine đang khởi động. Vui lòng thử lại sau vài giây!")
            return redirect(url_for('phan_loai'))

        except Exception as e:
            flash("Lỗi kết nối AI: Hãy kiểm tra URL Engine của bạn.")
            return redirect(url_for('phan_loai'))
            
    return render_template('nhan_dien_anh.html', prediction=None)
    
@app.route('/api/feedback', methods=['POST'])
def save_feedback():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Yêu cầu đăng nhập"}), 401
    
    data = request.json
    try:
        feedback_entry = {
            "username": session['user'],
            "image_data": data.get('image_base64'), # Chuỗi ảnh mã hóa
            "ai_prediction": data.get('ai_prediction'),
            "user_label": data.get('user_label'),
            "is_satisfied": data.get('is_satisfied'),
            "timestamp": time.time()
        }
        
        mongo.db.user_feedbacks.insert_one(feedback_entry)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        confirm = request.form.get('passwordconfirm')

        if not username or not email or not password:
            flash("Không được để trống thông tin!"); return redirect(url_for('signup'))

        if password != confirm:
            flash("Mật khẩu xác nhận không khớp!"); return redirect(url_for('signup'))
        
        # KIỂM TRA TRÙNG LẶP SÂU
        existing_user = mongo.db.users.find_one({
            "$or": [{"username": username}, {"email": email}]
        })
        
        if existing_user:
            flash("Tên đăng nhập hoặc Email này đã tồn tại!"); return redirect(url_for('signup'))
            
        mongo.db.users.insert_one({
            "username": username, 
            "email": email, 
            "password": generate_password_hash(password)
        })
        flash("Đăng ký thành công! Mời bạn đăng nhập.")
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = mongo.db.users.find_one({
            "$or": [{"username": identity}, {"email": identity}]
        })

        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session['user'] = user['username']
            return redirect(url_for('home'))
            
        flash("Thông tin tài khoản hoặc mật khẩu không chính xác!")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Bạn đã đăng xuất thành công.")
    return redirect(url_for('landing'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)