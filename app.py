from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

messages = []
banned_users = set()
muted_users = set()

ADMIN_NICKNAME = "Admin"
ADMIN_PASSWORD = "sifre123"

admin_sessions = {}  # ip -> admin yetkisi

@app.route('/')
def nickname():
    return render_template('nickname.html')

@app.route('/admin_login')
def admin_login():
    return render_template('admin_login.html')

@app.route('/chat')
def chat():
    nickname = request.args.get('nickname', '').strip()
    password = request.args.get('password', '')

    if not nickname:
        return redirect(url_for('nickname'))

    if nickname == ADMIN_NICKNAME:
        if password != ADMIN_PASSWORD:
            return redirect(url_for('admin_login'))
        admin_sessions[request.remote_addr] = True
    else:
        admin_sessions.pop(request.remote_addr, None)

    if nickname in banned_users:
        return "Banlandınız.", 403

    return render_template('chat.html', nickname=nickname, messages=messages)


@socketio.on('send_message')
def handle_send_message(data):
    text = data.get('text', '').strip()
    nickname = data.get('nickname')
    user_ip = request.remote_addr

    if not text:
        return

    if nickname in banned_users:
        emit('receive_message', {'nickname': 'Sistem', 'text': 'Banlandığınız için mesaj gönderemezsiniz.'}, to=request.sid)
        return

    if nickname in muted_users:
        emit('receive_message', {'nickname': 'Sistem', 'text': 'Sessize alındınız, mesaj gönderemezsiniz.'}, to=request.sid)
        return

    is_admin = admin_sessions.get(user_ip, False)

    if text.startswith('/'):
        parts = text.split()
        cmd = parts[0].lower()

        if is_admin:
            # Admin komutları
            if cmd == '/reset':
                messages.clear()
                emit('chat_cleared', broadcast=True)
                return

            elif cmd == '/exit':
                emit('exit_chat', to=request.sid)
                return

            elif cmd == '/ip':
                emit('receive_message', {'nickname': 'Sistem', 'text': f'Admin IP: {user_ip}'}, to=request.sid)
                return

            elif cmd == '/ban' and len(parts) == 2:
                target = parts[1]
                banned_users.add(target)
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} banlandı.'}, broadcast=True)
                return

            elif cmd == '/mute' and len(parts) == 2:
                target = parts[1]
                muted_users.add(target)
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} sessize alındı.'}, broadcast=True)
                return

            elif cmd in ['/help', '/?']:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Admin komutları: /reset, /exit, /ip, /ban <nick>, /mute <nick>, /help'}, to=request.sid)
                return

            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Bilinmeyen komut. /help yazınız.'}, to=request.sid)
                return

        else:
            # Normal kullanıcı komutları
            if cmd in ['/help', '/?']:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Kullanılabilir komutlar: /help, /exit'}, to=request.sid)
                return

            elif cmd == '/exit':
                emit('exit_chat', to=request.sid)
                return

            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Bilinmeyen komut. /help yazınız.'}, to=request.sid)
                return

    # Normal mesaj
    messages.append({'nickname': nickname, 'text': text})
    emit('receive_message', {'nickname': nickname, 'text': text}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

