import json
import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, disconnect

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gizlisifre'
socketio = SocketIO(app, manage_session=False)

USER_DB_FILE = 'users.json'

messages = []
users = {}          # sid -> nickname
user_ips = {}       # nickname -> ip
banned_users = set()
muted_users = set()

ADMIN_PASSWORD = "9980"

def load_users():
    if not os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, 'w') as f:
            json.dump({}, f)
    with open(USER_DB_FILE, 'r') as f:
        return json.load(f)

def save_users(users_db):
    with open(USER_DB_FILE, 'w') as f:
        json.dump(users_db, f)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['POST'])
def register():
    nickname = request.form.get('nickname').strip()
    password = request.form.get('password').strip()

    if not nickname or not password:
        return "Nickname ve şifre gerekli.", 400

    if nickname.lower() == 'admin':
        return "Admin kullanıcı adı kullanılamaz.", 400

    users_db = load_users()
    if nickname in users_db:
        return "Bu nickname zaten alınmış.", 400

    users_db[nickname] = password
    save_users(users_db)

    session['nickname'] = nickname
    session['is_admin'] = False

    return redirect(url_for('chat'))

@app.route('/login', methods=['POST'])
def login():
    nickname = request.form.get('nickname').strip()
    password = request.form.get('password').strip()

    if not nickname or not password:
        return "Nickname ve şifre gerekli.", 400

    if nickname.lower() == 'admin':
        if password != ADMIN_PASSWORD:
            return "Admin şifresi yanlış.", 403
        session['nickname'] = 'admin'
        session['is_admin'] = True
        return redirect(url_for('chat'))

    users_db = load_users()
    if nickname not in users_db:
        return "Böyle bir kullanıcı yok.", 403

    if users_db[nickname] != password:
        return "Şifre yanlış.", 403

    if nickname in banned_users:
        return "Banlandınız.", 403

    session['nickname'] = nickname
    session['is_admin'] = False

    return redirect(url_for('chat'))

@app.route('/chat')
def chat():
    nickname = session.get('nickname')
    if not nickname:
        return redirect(url_for('home'))
    is_admin = session.get('is_admin', False)
    return render_template('chat.html', nickname=nickname, admin=is_admin)

@socketio.on('join')
def on_join(data):
    sid = request.sid
    nickname = session.get('nickname')
    ip = request.remote_addr

    if not nickname:
        disconnect()
        return

    if nickname in banned_users:
        disconnect()
        return

    users[sid] = nickname
    user_ips[nickname] = ip

    msg = f"{nickname} katıldı."
    messages.append(msg)
    emit('message', {'msg': msg, 'admin': False}, broadcast=True)

    for m in messages:
        emit('message', {'msg': m, 'admin': False})

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    nickname = users.get(sid)
    if nickname:
        msg = f"{nickname} ayrıldı."
        messages.append(msg)
        emit('message', {'msg': msg, 'admin': False}, broadcast=True)
        users.pop(sid)
        user_ips.pop(nickname, None)
        muted_users.discard(nickname)

@socketio.on('message')
def handle_message(data):
    sid = request.sid
    nickname = users.get(sid)
    if not nickname:
        return

    text = data.get('msg', '').strip()
    if not text:
        return

    is_admin = session.get('is_admin', False)

    if is_admin:
        if text.startswith('/reset'):
            messages.clear()
            emit('message', {'msg': 'Sohbet temizlendi (reset).', 'admin': True}, broadcast=True)
            return

        if text.startswith('/ban '):
            target = text.split(' ', 1)[1].strip()
            if target:
                banned_users.add(target)
                emit('message', {'msg': f"Kullanıcı banlandı: {target}", 'admin': True}, broadcast=True)
                for sid_, nick_ in list(users.items()):
                    if nick_ == target:
                        emit('message', {'msg': 'Banlandığınız için bağlantınız kesildi.', 'admin': True}, room=sid_)
                        disconnect(sid_)
                return

        if text.startswith('/mute '):
            target = text.split(' ', 1)[1].strip()
            if target:
                muted_users.add(target)
                emit('message', {'msg': f"Kullanıcı susturuldu: {target}", 'admin': True}, broadcast=True)
                return

        if text.startswith('/unmute '):
            target = text.split(' ', 1)[1].strip()
            if target:
                muted_users.discard(target)
                emit('message', {'msg': f"Kullanıcının susturulması kaldırıldı: {target}", 'admin': True}, broadcast=True)
                return

        if text.startswith('/exit'):
            emit('message', {'msg': f"Admin {nickname} çıkıyor.", 'admin': True}, broadcast=True)
            disconnect()
            return

    if nickname in muted_users:
        emit('message', {'msg': 'Susturuldunuz, mesaj gönderemezsiniz.', 'admin': True}, room=sid)
        return

    full_msg = f"{nickname}: {text}"
    messages.append(full_msg)
    emit('message', {'msg': full_msg, 'admin': False}, broadcast=True)

# 🔧 Railway'de çalışması için PORT ve 0.0.0.0 ayarı önemli
if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, host='0.0.0.0', port=port)

