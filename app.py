from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gizlisifre'
socketio = SocketIO(app)

# Veritabanı yerine basit dictler
users = {}  # sid -> nickname
user_passwords = {}  # nickname -> password
banned = set()
muted = set()
ips = {}  # sid -> ip

ADMIN_NICK = "admin"
ADMIN_PASSWORD = "9980"

messages = []

# Oturum kontrol decoratorü
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'nickname' not in session:
            return redirect(url_for('login'))
        if session['nickname'] in banned:
            return "Yasaklısınız.", 403
        return f(*args, **kwargs)
    return decorated

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        password = request.form.get('password')
        
        if not nickname or not password:
            return render_template('login.html', error="Nickname ve şifre zorunlu.")
        
        if nickname.lower() == ADMIN_NICK:
            if password != ADMIN_PASSWORD:
                return render_template('login.html', error="Admin şifresi yanlış.")
            session['nickname'] = ADMIN_NICK
            session['is_admin'] = True
            return redirect(url_for('chat'))
        else:
            # Kullanıcı daha önce giriş yaptıysa ve şifresi kayıtlıysa kontrol et
            if nickname in user_passwords:
                if user_passwords[nickname] != password:
                    return render_template('login.html', error="Şifre yanlış.")
            else:
                # Yeni kullanıcı, şifreyi kaydet
                user_passwords[nickname] = password
            
            session['nickname'] = nickname
            session['is_admin'] = False
            return redirect(url_for('chat'))
    else:
        return render_template('login.html')

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html', nickname=session['nickname'], admin=session.get('is_admin', False))

@socketio.on('join')
def on_join(data):
    sid = request.sid
    nick = session.get('nickname')
    is_admin = session.get('is_admin', False)
    users[sid] = nick
    ips[sid] = request.remote_addr
    msg = f"{nick} katıldı."
    messages.append(msg)
    emit('message', {'msg': msg, 'admin': False}, broadcast=True)
    # Katılan kişiye önceki mesajları gönder
    for m in messages:
        emit('message', {'msg': m, 'admin': False})

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    nick = users.get(sid)
    if nick:
        msg = f"{nick} ayrıldı."
        messages.append(msg)
        emit('message', {'msg': msg, 'admin': False}, broadcast=True)
        users.pop(sid)
        ips.pop(sid, None)
        muted.discard(nick)
        banned.discard(nick)

@socketio.on('send_message')
def on_message(data):
    sid = request.sid
    nick = users.get(sid)
    msg = data.get('msg')
    if not nick or not msg:
        return
    if nick in muted:
        emit('message', {'msg': 'Susturuldunuz, mesaj gönderemezsiniz.', 'admin': True}, room=sid)
        return
    
    # Komutlar
    if msg.startswith('/'):
        if session.get('is_admin', False):
            # Admin komutları
            parts = msg.strip().split(' ', 2)
            cmd = parts[0].lower()

            if cmd == '/reset':
                messages.clear()
                emit('message', {'msg': 'Sohbet sıfırlandı.', 'admin': True}, broadcast=True)
            elif cmd == '/ip' and len(parts) > 1:
                target = parts[1]
                ip = None
                for s, n in users.items():
                    if n == target:
                        ip = ips.get(s)
                        break
                if ip:
                    emit('message', {'msg': f"{target} IP'si: {ip}", 'admin': True}, room=sid)
                else:
                    emit('message', {'msg': "Kullanıcı bulunamadı.", 'admin': True}, room=sid)
            elif cmd == '/ipban' and len(parts) > 1:
                target = parts[1]
                for s, n in users.items():
                    if n == target:
                        banned.add(target)
                        emit('message', {'msg': f"{target} yasaklandı (IP ban).", 'admin': True}, broadcast=True)
                        disconnect(sid=s)
                        break
            elif cmd == '/unipban' and len(parts) > 1:
                target = parts[1]
                if target in banned:
                    banned.remove(target)
                    emit('message', {'msg': f"{target} yasaktan çıkarıldı.", 'admin': True}, room=sid)
                else:
                    emit('message', {'msg': "Kullanıcı yasaklı değil.", 'admin': True}, room=sid)
            elif cmd == '/mute' and len(parts) > 1:
                target = parts[1]
                muted.add(target)
                emit('message', {'msg': f"{target} susturuldu.", 'admin': True}, broadcast=True)
            elif cmd == '/unmute' and len(parts) > 1:
                target = parts[1]
                if target in muted:
                    muted.remove(target)
                    emit('message', {'msg': f"{target} susturması kaldırıldı.", 'admin': True}, broadcast=True)
                else:
                    emit('message', {'msg': "Kullanıcı susturulmamış.", 'admin': True}, room=sid)
            elif cmd == '/exit':
                emit('message', {'msg': 'Admin çıkış yaptı.', 'admin': True}, broadcast=True)
                disconnect()
            else:
                emit('message', {'msg': "Bilinmeyen komut.", 'admin': True}, room=sid)
        else:
            # Kullanıcı komutları
            cmd = msg.lower()
            if cmd in ['/?', '/help']:
                help_text = "/? veya /help - Yardım\n/exit - Çıkış"
                emit('message', {'msg': help_text, 'admin': True}, room=sid)
            elif cmd == '/exit':
                emit('message', {'msg': f"{nick} çıkış yaptı.", 'admin': True}, broadcast=True)
                disconnect()
            else:
                emit('message', {'msg': "Bilinmeyen komut.", 'admin': True}, room=sid)
        return

    # Normal mesaj
    messages.append(f"{nick}: {msg}")
    emit('message', {'msg': f"{nick}: {msg}", 'admin': False}, broadcast=True)


if __name__ == '__main__':
    socketio.run(app, debug=True)

