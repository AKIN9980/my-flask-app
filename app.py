import os
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
from flask_session import Session

app = Flask(__name__)
app.secret_key = 'gizli-anahtar'  # Burası gizli ve uzun olmalı
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# SocketIO, eventlet ile uyumlu çalışacak şekilde
socketio = SocketIO(app, manage_session=False, async_mode='eventlet')

messages = []  # Tüm mesajlar burada tutuluyor (basit demo için, prod’da db gerekir)

@app.route('/')
def index():
    if 'nickname' not in session:
        return render_template('nickname.html')
    return render_template('chat.html', nickname=session['nickname'])

@app.route('/set-nickname', methods=['POST'])
def set_nickname():
    nickname = request.form.get('nickname')
    if nickname:
        session['nickname'] = nickname
        return ('', 204)
    return ('Bad Request', 400)

@socketio.on('connect')
def on_connect():
    # Bağlanan kişiye tüm mesajları yolla
    emit('load_messages', messages)

@socketio.on('send_message')
def handle_message(data):
    msg = {
        'nickname': session.get('nickname', 'Anonim'),
        'text': data['text']
    }
    messages.append(msg)
    emit('receive_message', msg, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)

