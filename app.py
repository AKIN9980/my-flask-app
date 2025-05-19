from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, disconnect
from flask_session import Session

app = Flask(__name__)
app.secret_key = 'gizli-anahtar'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
socketio = SocketIO(app, manage_session=False)

messages = []
banned_ips = set()
muted_users = set()
used_nicknames = set()

ADMIN_PASSWORD = "9980"

def is_admin():
    return session.get('nickname') == 'Admin'

@app.route('/')
def index():
    if 'nickname' not in session:
        return render_template('nickname.html')
    return render_template('chat.html', nickname=session['nickname'])

@app.route('/set-nickname', methods=['POST'])
def set_nickname():
    nickname = request.form.get('nickname')
    password = request.form.get('password', None)

    if not nickname:
        return 'Nickname boş olamaz', 400
    if nickname in used_nicknames:
        return 'Bu takma ad kullanılıyor', 400

    if nickname == "Admin":
        if password != ADMIN_PASSWORD:
            return 'Şifre yanlış', 403

    session['nickname'] = nickname
    used_nicknames.add(nickname)
    return ('', 204)

@socketio.on('connect')
def on_connect():
    user_ip = request.remote_addr
    if user_ip in banned_ips:
        disconnect()
        return
    emit('load_messages', messages)

@socketio.on('disconnect')
def on_disconnect():
    nickname = session.get('nickname')
    if nickname in used_nicknames:
        used_nicknames.remove(nickname)

@socketio.on('send_message')
def handle_message(data):
    user_ip = request.remote_addr
    nickname = session.get('nickname', 'Anonim')

    if user_ip in banned_ips:
        emit('receive_message', {'nickname': 'Sistem', 'text': 'Engellendiniz, mesaj gönderemezsiniz.'})
        return

    if nickname in muted_users:
        emit('receive_message', {'nickname': 'Sistem', 'text': 'Susturuldunuz, mesaj gönderemezsiniz.'})
        return

    text = data['text'].strip()

    if is_admin() and text.startswith('/'):
        parts = text.split()
        cmd = parts[0].lower()

        if cmd == '/reset':
            messages.clear()
            emit('load_messages', messages, broadcast=True)
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Sohbet temizlendi!'}, broadcast=True)
            return

        elif cmd == '/ban' and len(parts) == 2:
            target_nick = parts[1]
            # Banlanacak kullanıcının IP'sini bul
            banned_ip = None
            for sid, sess in socketio.server.manager.get_participants('/', '/'):
                # Bu kısım Flask-SocketIO'da client IP'yi doğrudan almak zor
                # Basit örnek için mesajda kullanıcı IP'sini tutmuyorsak, IP bulma kısmı zor
                # Bu yüzden burada ip bulma için ekstra kod gerekir.
                # Şimdilik burayı boş bırakıyorum, gerçek projede IP takibi yapılmalı.
                pass
            # Örnek olarak bu komutu sadece nick listesinden ipyi bulup eklemeyebiliriz
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{target_nick} banlandı (IP ban sistemi eksik).'}, broadcast=True)
            return

        elif cmd == '/mute' and len(parts) == 2:
            target = parts[1]
            muted_users.add(target)
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} susturuldu.'}, broadcast=True)
            return

        elif cmd == '/unmute' and len(parts) == 2:
            target = parts[1]
            muted_users.discard(target)
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} susturulma kaldırıldı.'}, broadcast=True)
            return

        elif cmd == '/unban' and len(parts) == 2:
            # Aynı şekilde IP ban kaldıramayız burada kolayca
            emit('receive_message', {'nickname': 'Sistem', 'text': f'Ban kaldırma sistemi eksik.'}, broadcast=True)
            return

        elif cmd == '/ip' and len(parts) == 2:
            # IP bulma komutu - sadece admin
            target = parts[1]
            # IP bilgisi tutulmuyorsa, örneğin: messages'de ip yok, socketio sessionda yok
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} IP bilgisi bulunamadı (IP takibi eksik).'})
            return

        elif cmd == '/exit':
            # Admin /exit yazarsa sadece çıkış yapacak
            if is_admin():
                session.clear()
                disconnect()
                return

        elif cmd == '/help' or cmd == '/?':
            commands = """
            Komutlar:
            /reset - Sohbeti temizle (admin)
            /ban [nickname] - Kullanıcıyı banla (IP ban sistemi eksik)
            /unban [nickname] - Ban kaldır (eksik)
            /mute [nickname] - Sustur
            /unmute [nickname] - Susturmayı kaldır
            /ip [nickname] - Kullanıcı IP göster (eksik)
            /exit - Çıkış yap
            """
            emit('receive_message', {'nickname': 'Sistem', 'text': commands})
            return

        else:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Bilinmeyen komut. /help ile yardım alın.'})
            return

    # Normal mesaj ekle
    msg = {'nickname': nickname, 'text': text, 'admin': is_admin()}
    messages.append(msg)
    emit('receive_message', msg, broadcast=True)


if __name__ == '__main__':
    socketio.run(app)

