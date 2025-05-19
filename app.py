from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, disconnect

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gizlisifre'
socketio = SocketIO(app, manage_session=False)

messages = []
users = {}          # sid -> nickname
user_ips = {}       # nickname -> ip
banned_users = set()
muted_users = set()

ADMIN_PASSWORD = "9980"

@app.route('/')
def nickname():
    return render_template('nickname.html')

@app.route('/login', methods=['POST'])
def login():
    nickname = request.form.get('nickname').strip()
    password = request.form.get('password', '').strip()

    if not nickname:
        return redirect(url_for('nickname'))

    if nickname.lower() == 'admin':
        if password != ADMIN_PASSWORD:
            return redirect(url_for('nickname'))
        session['is_admin'] = True
    else:
        session['is_admin'] = False

    # Ban kontrolü
    ip = request.remote_addr
    if nickname in banned_users:
        return "Banlandınız.", 403

    # Şifre sorgulama - örnek: kullanıcı daha önce girmişse sessionda şifresi tutuluyor
    # Bu örnekte basit, ileride db ile değiştirilebilir.
    if 'passwords' not in session:
        session['passwords'] = {}
    stored_pw = session['passwords'].get(nickname)
    if stored_pw and stored_pw != password:
        return "Şifre yanlış.", 403
    elif not stored_pw:
        session['passwords'][nickname] = password

    session['nickname'] = nickname
    return redirect(url_for('chat'))

@app.route('/chat')
def chat():
    nickname = session.get('nickname')
    if not nickname:
        return redirect(url_for('nickname'))
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

    # Yeni gelen kişiye geçmiş mesajları gönder
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
        banned_users.discard(nickname)

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

    # Admin komutları
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
                # Banlanan kişi varsa onun bağlantısını kopar
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

    # Mesajı tüm kullanıcılara yayınla
    full_msg = f"{nickname}: {text}"
    messages.append(full_msg)
    emit('message', {'msg': full_msg, 'admin': False}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)

