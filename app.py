from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import os
import time
import uuid
from datetime import datetime

app = Flask(__name__)
app.config['DATABASE'] = 'chat.db'

# 确保数据库目录存在
os.makedirs(os.path.dirname(os.path.abspath(app.config['DATABASE'])), exist_ok=True)

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
        conn.commit()

# 初始化数据库
init_db()

@app.route('/')
def index():
    # 将首页作为静态文件发送
    return send_from_directory('.', 'index.html')

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)