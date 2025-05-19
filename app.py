from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gizlisifre'
socketio = SocketIO(app)

messages = []
users = {}  # sid -> nickname
banned_ips = set()
banned_users = set()
muted_users = set()
user_passwords = {}  # nickname -> hashed_password

ADMIN_PASSWORD = "9980"

def is_banned(ip, nickname):
    return ip in banned_ips or nickname in banned_users

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nickname = request.form.get('nickname').strip()
        password = request.form.get('password').strip()
        ip = request.remote_addr

        if is_banned(ip, nickname):
            return "Banlandınız.", 403

        # Admin kontrolü
        if nickname.lower() == "admin":
            if password != ADMIN_PASSWORD:
                return "Admin şifresi yanlış.", 403
            session['nickname'] = nickname
            session['is_admin'] = True
            return redirect(url_for('chat'))

        # Kullanıcı şifre kontrolü
        if nickname in user_passwords:
            if not check_password_hash(user_passwords[nickname], password):
                return "Şifre yanlış.", 403
        else:
            # Yeni kullanıcı, kayıt ol
            user_passwords[nickname] = generate_password_hash(password)

        session['nickname'] = nickname
        session['is_admin'] = False
        return redirect(url_for('chat'))

    return render_template('login.html')


@app.route('/chat')
def chat():
    if 'nickname' not in session:
        return redirect(url_for('login'))

    nickname = session['nickname']
    ip = request.remote_addr

    if is_banned(ip, nickname):
        return "Banlandınız.", 403

    return render_template('chat.html', nickname=nickname, admin=session.get('is_admin', False), messages=messages)

@socketio.on('join')
def on_join(data):
    sid = request.sid
    nickname = session.get('nickname')
    if not nickname:
        return

    users[sid] = nickname

    msg = f"{nickname} katıldı."
    messages.append(msg)
    emit('message', {'msg': msg, 'admin': False}, broadcast=True)

@socketio.on('message')
def handle_message(data):
    sid = request.sid
    nickname = users.get(sid)
    if not nickname:
        return

    text = data.get('msg', '').strip()

    # Admin komutları
    if session.get('is_admin'):
        if text.startswith('/reset'):
            messages.clear()
            emit('message', {'msg': 'Sohbet temizlendi (reset).', 'admin': True}, broadcast=True)
            return

        if text.startswith('/ipban '):
            target = text.split(' ')[1]
            banned_ips.add(target)
            emit('message', {'msg': f"IP banlandı: {target}", 'admin': True}, broadcast=True)
            return

        if text.startswith('/ban '):
            target = text.split(' ')[1]
            banned_users.add(target)
            emit('message', {'msg': f"Kullanıcı banlandı: {target}", 'admin': True}, broadcast=True)
            return

        if text.startswith('/unban '):
            target = text.split(' ')[1]
            banned_users.discard(target)
            emit('message', {'msg': f"Kullanıcının banı kaldırıldı: {target}", 'admin': True}, broadcast=True)
            return

        if text.startswith('/mute '):
            target = text.split(' ')[1]
            muted_users.add(target)
            emit('message', {'msg': f"Kullanıcı susturuldu: {target}", 'admin': True}, broadcast=True)
            return

        if text.startswith('/unmute '):
            target = text.split(' ')[1]
            muted_users.discard(target)
            emit('message', {'msg': f"Kullanıcının susturulması kaldırıldı: {target}", 'admin': True}, broadcast=True)
            return

        if text.startswith('/exit'):
            emit('message', {'msg': f"Admin {nickname} çıkıyor.", 'admin': True}, broadcast=True)
            disconnect()
            return

    if nickname in muted_users:
        emit('message', {'msg': 'Susturuldunuz, mesaj gönderemezsiniz.', 'admin': True})
        return

    messages.append(f"{nickname}: {text}")
    emit('message', {'msg': f"{nickname}: {text}", 'admin': False}, broadcast=True)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    nickname = users.get(sid)
    if nickname:
        msg = f"{nickname} ayrıldı."
        messages.append(msg)
        emit('message', {'msg': msg, 'admin': False}, broadcast=True)
        users.pop(sid, None)

