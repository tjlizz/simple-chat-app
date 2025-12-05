from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import os
import time
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['DATABASE'] = 'chat.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 确保数据库目录存在
os.makedirs(os.path.dirname(os.path.abspath(app.config['DATABASE'])), exist_ok=True)
# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS uploaded_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        )
        ''')
        conn.commit()

# 初始化数据库
init_db()

@app.route('/')
def index():
    # 将首页作为静态文件发送
    return send_from_directory('.', 'index.html')


@app.route('/upload')
def upload_page():
    # 将上传页面作为静态文件发送
    return send_from_directory('.', 'upload.html')

# 移除了清理消息的API端点，保留所有消息在数据库中

@app.route('/api/messages', methods=['GET'])
def get_messages():
    # 获取时间戳参数，只返回该时间戳之后的消息
    last_timestamp = request.args.get('after', 0, type=int)
    
    # 计算1小时前的时间戳 (毫秒)
    one_hour_ago = int(time.time() * 1000) - (60 * 60 * 1000)
    
    with get_db_connection() as conn:
        messages = conn.execute(
            'SELECT * FROM messages WHERE timestamp > ? AND timestamp > ? ORDER BY timestamp ASC',
            (last_timestamp, one_hour_ago)
        ).fetchall()
        
    return jsonify([{
        'id': message['id'],
        'user_id': message['user_id'],
        'message': message['message'],
        'timestamp': message['timestamp'],
        'is_self': False  # 在客户端处理
    } for message in messages])


@app.route('/img/bg.png')
def serve_background():
    # 获取用户ID参数
    user_id = request.args.get('user_id')

    if user_id:
        with get_db_connection() as conn:
            # 查找用户最近上传的图片
            latest_image = conn.execute(
                'SELECT filename FROM uploaded_images WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1',
                (user_id,)
            ).fetchone()

            if latest_image:
                # 返回用户上传的图片
                upload_folder = os.path.join('uploads', user_id)
                return send_from_directory(upload_folder, latest_image['filename'])

    # 如果没有用户上传的图片，返回默认背景图片
    return send_from_directory('img', 'bg.png')


@app.route('/api/messages', methods=['POST'])
def send_message():
    data = request.json
    
    if not data or not data.get('message') or not data.get('user_id'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    user_id = data.get('user_id')
    message = data.get('message')
    timestamp = int(time.time() * 1000)  # 毫秒时间戳
    
    with get_db_connection() as conn:
        conn.execute(
            'INSERT INTO messages (user_id, message, timestamp) VALUES (?, ?, ?)',
            (user_id, message, timestamp)
        )
        conn.commit()
    
    return jsonify({'success': True, 'timestamp': timestamp})


@app.route('/api/upload', methods=['POST'])
def upload_file():
    # 获取用户ID
    user_id = request.form.get('user_id')

    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400

    # 检查是否有文件上传
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    # 检查是否选择了文件
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # 验证文件类型
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    # 生成安全的文件名
    filename = secure_filename(file.filename)
    # 添加时间戳前缀以避免文件名冲突
    timestamp = int(time.time() * 1000)
    filename = f"{timestamp}_{filename}"

    # 创建用户专属的上传目录
    user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    os.makedirs(user_upload_dir, exist_ok=True)

    # 保存文件
    file_path = os.path.join(user_upload_dir, filename)
    file.save(file_path)

    # 保存到数据库
    with get_db_connection() as conn:
        conn.execute(
            'INSERT INTO uploaded_images (user_id, filename, timestamp) VALUES (?, ?, ?)',
            (user_id, filename, timestamp)
        )
        conn.commit()

    return jsonify({
        'success': True,
        'filename': filename,
        'timestamp': timestamp,
        'message': 'File uploaded successfully'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)