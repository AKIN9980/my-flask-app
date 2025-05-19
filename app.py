import os
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, disconnect
from flask_session import Session

app = Flask(__name__)
app.secret_key = 'gizli-anahtar'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

socketio = SocketIO(app, manage_session=False, async_mode='eventlet')

messages = []
banned_ips = set()
muted_ips = set()
taken_nicknames = set()

ADMIN_PASSWORD = '9980'

COMMAND_LIST = """
KOMUTLAR:
/ban <IP>         - IP banla (admin)
/unban <IP>       - Ban kaldır (admin)
/mute <IP>        - IP sessize al (admin)
/unmute <IP>      - Sessizliği kaldır (admin)
/reset            - Sohbeti sıfırla (admin)
/exit             - Admin yetkilerini bırak veya kullanıcı çıkış yapar
/help veya /?     - Komut listesini göster
/ip <nickname>    - Kullanıcının IP adresini göster (admin)
"""

def get_ip_by_nickname(nickname):
    # Bu örnekte sadece bağlı socketlardan ip buluyoruz.
    # Daha kapsamlı yönetim için bağlantı izleme gerekebilir.
    for sid, user_data in connected_users.items():
        if user_data['nickname'] == nickname:
            return user_data['ip']
    return None

connected_users = {}  # sid: {'nickname':..., 'ip':..., 'is_admin':...}

@app.route('/')
def index():
    if 'nickname' not in session:
        return render_template('nickname.html')
    return render_template('chat.html', nickname=session['nickname'], is_admin=session.get('is_admin', False))

@app.route('/set-nickname', methods=['POST'])
def set_nickname():
    nickname = request.form.get('nickname')
    if not nickname:
        return ('Bad Request', 400)

    if nickname in taken_nicknames:
        return ('Bu takma ad kullanılıyor.', 409)

    if nickname.lower() == 'admin':
        password = request.form.get('password')
        if password != ADMIN_PASSWORD:
            return ('Yanlış şifre', 401)
        session['is_admin'] = True
    else:
        session['is_admin'] = False

    session['nickname'] = nickname
    taken_nicknames.add(nickname)
    return ('', 204)

@socketio.on('connect')
def on_connect():
    ip = request.remote_addr
    sid = request.sid
    nickname = session.get('nickname', 'Anonim')
    is_admin = session.get('is_admin', False)

    if ip in banned_ips:
        disconnect()
        return

    connected_users[sid] = {'nickname': nickname, 'ip': ip, 'is_admin': is_admin}
    emit('load_messages', messages)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    user = connected_users.get(sid)
    if user:
        # Eğer admin çıkış yapmadıysa, kullanıcı çıkınca nickname hala dolu kalıyor, sadece admin değilse nickname silinsin
        if not user['is_admin']:
            taken_nicknames.discard(user['nickname'])
        connected_users.pop(sid, None)

@socketio.on('send_message')
def handle_message(data):
    ip = request.remote_addr
    sid = request.sid
    user = connected_users.get(sid)

    if not user:
        return

    if ip in banned_ips:
        return

    if ip in muted_ips:
        return

    nickname = user['nickname']
    is_admin = user['is_admin']
    text = data['text'].strip()

    if text.startswith('/'):
        parts = text.split(' ', 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ''

        if cmd in ['/help', '/?']:
            emit('receive_message', {'nickname': 'SYSTEM', 'text': COMMAND_LIST}, room=sid)
            return

        if cmd == '/exit':
            if is_admin:
                # Admin yetkisini bırak ama nickname kalır, is_admin false olur
                user['is_admin'] = False
                session['is_admin'] = False
                emit('receive_message', {'nickname': 'SYSTEM', 'text': f"{nickname} artık admin değil."}, room=sid)
                # nickname silinmez
                return
            else:
                # Normal kullanıcı çıkış yapıyor
                taken_nicknames.discard(nickname)
                # Oturumu ve bağlantıyı kes
                session.pop('nickname', None)
                session.pop('is_admin', None)
                emit('receive_message', {'nickname': 'SYSTEM', 'text': f"{nickname} sohbetten çıktı ve nickname serbest kaldı."}, broadcast=True)
                disconnect(sid=sid)
                return

        if not is_admin:
            emit('receive_message', {'nickname': 'SYSTEM', 'text': 'Bu komutu kullanmak için admin olmalısınız.'}, room=sid)
            return

        # Admin komutları
        if cmd == '/ban':
            banned_ips.add(arg)
            emit('receive_message', {'nickname': 'SYSTEM', 'text': f'IP {arg} banlandı.'}, broadcast=True)
            return
        elif cmd == '/unban':
            banned_ips.discard(arg)
            emit('receive_message', {'nickname': 'SYSTEM', 'text': f'IP {arg} banı kaldırıldı.'}, broadcast=True)
            return
        elif cmd == '/mute':
            muted_ips.add(arg)
            emit('receive_message', {'nickname': 'SYSTEM', 'text': f'IP {arg} sessize alındı.'}, broadcast=True)
            return
        elif cmd == '/unmute':
            muted_ips.discard(arg)
            emit('receive_message', {'nickname': 'SYSTEM', 'text': f'IP {arg} sessizliği kaldırıldı.'}, broadcast=True)
            return
        elif cmd == '/reset':
            messages.clear()
            emit('receive_message', {'nickname': 'SYSTEM', 'text': 'Sohbet sıfırlandı.'}, broadcast=True)
            emit('load_messages', messages, broadcast=True)
            return
        elif cmd == '/ip':
            # arg olarak nickname alır, IP gösterir
            if not arg:
                emit('receive_message', {'nickname': 'SYSTEM', 'text': 'Kullanıcı adını girin: /ip <nickname>'}, room=sid)
                return
            ip_found = get_ip_by_nickname(arg)
            if ip_found:
                emit('receive_message', {'nickname': 'SYSTEM', 'text': f'{arg} kullanıcısının IP adresi: {ip_found}'}, room=sid)
            else:
                emit('receive_message', {'nickname': 'SYSTEM', 'text': f'{arg} kullanıcısı bulunamadı.'}, room=sid)
            return
        else:
            emit('receive_message', {'nickname': 'SYSTEM', 'text': 'Bilinmeyen komut.'}, room=sid)
            return

    # Normal mesaj
    display_name = f'[ADMIN] {nickname}' if is_admin else nickname
    msg = {'nickname': display_name, 'text': text}
    messages.append(msg)
    emit('receive_message', msg, broadcast=True)

