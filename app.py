from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, disconnect
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

messages = []
users = {}  # nickname -> sid
banned_ips = set()
muted_ips = set()
admin_password = "9980"

admins = set()  # sid listesi adminler için

@app.route('/')
def index():
    return render_template('nickname.html')

@app.route('/chat')
def chat():
    nickname = request.args.get('nickname')
    if not nickname:
        return redirect(url_for('index'))
    # Eğer banlı IP ise reddet
    ip = request.remote_addr
    if ip in banned_ips:
        return "IP'niz yasaklandı."
    return render_template('chat.html', nickname=nickname)

@socketio.on('connect')
def on_connect():
    ip = request.remote_addr
    if ip in banned_ips:
        disconnect()
        return

@socketio.on('join')
def on_join(data):
    nickname = data.get('nickname')
    sid = request.sid
    ip = request.remote_addr

    # Eğer ip mute ise sessiz mod
    if ip in muted_ips:
        emit('muted', {'msg': 'Susturuldunuz.'}, room=sid)

    # Nickname kullanımdaysa reddet
    if nickname in users.values():
        emit('nickname_taken', room=sid)
        disconnect()
        return

    # Admin kontrolü
    if nickname.lower() == 'admin':
        emit('request_password', room=sid)
        return

    users[nickname] = sid
    emit('load_messages', messages, room=sid)
    emit('receive_message', {'nickname': 'Sistem', 'text': f'{nickname} sohbete katıldı.'}, broadcast=True)

@socketio.on('admin_auth')
def admin_auth(data):
    sid = request.sid
    password = data.get('password')
    nickname = data.get('nickname')

    if password == admin_password:
        users[nickname] = sid
        admins.add(sid)
        emit('load_messages', messages, room=sid)
        emit('receive_message', {'nickname': 'Sistem', 'text': f'Admin {nickname} sohbete katıldı.'}, broadcast=True)
    else:
        emit('auth_failed', room=sid)
        disconnect()

@socketio.on('send_message')
def on_message(data):
    sid = request.sid
    ip = request.remote_addr

    if ip in muted_ips:
        emit('receive_message', {'nickname': 'Sistem', 'text': 'Susturuldunuz, mesaj gönderemezsiniz.'}, room=sid)
        return

    # Kullanıcıyı bul
    nickname = None
    for n, s in users.items():
        if s == sid:
            nickname = n
            break
    if not nickname:
        emit('receive_message', {'nickname': 'Sistem', 'text': 'Lütfen önce nickname seçin.'}, room=sid)
        return

    text = data.get('text','').strip()
    if not text:
        return

    # Komutlar
    if text.startswith('/'):
        handle_command(nickname, sid, ip, text)
        return

    messages.append({'nickname': nickname, 'text': text})
    if len(messages) > 100:
        messages.pop(0)
    emit('receive_message', {'nickname': nickname, 'text': text}, broadcast=True)

def handle_command(nickname, sid, ip, text):
    global messages

    split_text = text.split()
    cmd = split_text[0].lower()

    # Herkesin kullanabildiği komutlar
    if cmd in ['/help', '/?']:
        help_text = (
            "/help veya /? : Komut listesini gösterir\n"
            "/exit : Çıkış yapar\n"
        )
        # Admin komutları
        if sid in admins:
            help_text += (
                "/ip <nickname> : Kullanıcının IP'sini gösterir\n"
                "/ban <nickname> : Kullanıcıyı banlar\n"
                "/mute <nickname> : Kullanıcıyı susturur\n"
                "/unmute <nickname> : Susturmayı kaldırır\n"
                "/reset : Sohbeti temizler\n"
            )
        emit('receive_message', {'nickname': 'Sistem', 'text': help_text}, room=sid)
        return

    if cmd == '/exit':
        # nickname sil, kullanıcıyı listeden çıkar, disconnect
        if nickname.lower() == 'admin' and sid in admins:
            # Admin sadece çıkış yapar, nickname silinmez
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Admin çıkış yaptı.'}, room=sid)
            disconnect()
            return
        # Normal kullanıcılar
        if nickname in users:
            del users[nickname]
        emit('receive_message', {'nickname': 'Sistem', 'text': f'{nickname} çıkış yaptı.'}, broadcast=True)
        disconnect()
        return

    if cmd == '/ip':
        if sid not in admins:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komutu sadece admin kullanabilir.'}, room=sid)
            return
        if len(split_text) < 2:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Kullanıcı adı yazmalısınız.'}, room=sid)
            return
        target = split_text[1]
        if target in users:
            # IP göster
            # Not: Flask içinde IP’yi buradan alıyoruz, güvenlik için sadece örnek
            # Gerçek IP’yi kaydetmek için kullanıcı join’de IP kaydetmeli
            emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} kullanıcısının IP'si: {request.remote_addr}"}, room=sid)
        else:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Kullanıcı bulunamadı.'}, room=sid)
        return

    if sid not in admins:
        emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komutu sadece admin kullanabilir.'}, room=sid)
        return

    # Admin komutları
    if cmd == '/ban':
        if len(split_text) < 2:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Banlamak için kullanıcı adı yazmalısınız.'}, room=sid)
            return
        target = split_text[1]
        if target in users:
            user_sid = users[target]
            banned_ips.add(request.remote_addr)
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} banlandı.'}, broadcast=True)
            disconnect_user(user_sid)
        else:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Kullanıcı bulunamadı.'}, room=sid)
        return

    if cmd == '/mute':
        if len(split_text) < 2:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Mute için kullanıcı adı yazmalısınız.'}, room=sid)
            return
        target = split_text[1]
        if target in users:
            target_ip = request.remote_addr  # IPyi join'de kaydetmek daha doğru
            muted_ips.add(target_ip)
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} susturuldu.'}, broadcast=True)
        else:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Kullanıcı bulunamadı.'}, room=sid)
        return

    if cmd == '/unmute':
        if len(split_text) < 2:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Unmute için kullanıcı adı yazmalısınız.'}, room=sid)
            return
        target = split_text[1]
        if target in users:
            target_ip = request.remote_addr
            if target_ip in muted_ips:
                muted_ips.remove(target_ip)
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} artık susturulmadı.'}, broadcast=True)
        else:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Kullanıcı bulunamadı.'}, room=sid)
        return

    if cmd == '/reset':
        messages = []
        emit('receive_message', {'nickname': 'Sistem', 'text': 'Sohbet temizlendi.'}, broadcast=True)
        emit('clear_chat', broadcast=True)
        return

def disconnect_user(sid):
    try:
        disconnect(sid=sid)
    except Exception:
        pass

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    nickname_to_remove = None
    for nickname, s in users.items():
        if s == sid:
            nickname_to_remove = nickname
            break
    if nickname_to_remove:
        del users[nickname_to_remove]
        emit('receive_message', {'nickname': 'Sistem', 'text': f'{nickname_to_remove} sohbetten ayrıldı.'}, broadcast=True)
    if sid in admins:
        admins.remove(sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

