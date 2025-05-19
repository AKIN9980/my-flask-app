from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, disconnect
from flask_session import Session

app = Flask(__name__)
app.secret_key = 'gizli-anahtar'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
socketio = SocketIO(app, manage_session=False)

messages = []
used_nicknames = set()
banned_ips = set()
muted_users = set()

ADMIN_NICKNAME = 'Admin'
ADMIN_PASSWORD = '9980'


def is_admin():
    return session.get('nickname') == ADMIN_NICKNAME and session.get('is_admin') == True


@app.route('/')
def index():
    if 'nickname' not in session:
        return render_template('nickname.html')
    return render_template('chat.html', nickname=session['nickname'], is_admin=is_admin())


@app.route('/set-nickname', methods=['POST'])
def set_nickname():
    nickname = request.form.get('nickname')
    password = request.form.get('password', '')

    if not nickname:
        return ('Nickname gerekli', 400)

    if nickname in used_nicknames:
        return ('Nickname kullanılıyor', 400)

    if nickname == ADMIN_NICKNAME:
        # Admin için şifre kontrolü
        if password != ADMIN_PASSWORD:
            return ('Admin şifresi yanlış', 401)
        session['is_admin'] = True
    else:
        session['is_admin'] = False

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
    # Nickname serbest bırakma işlemi
    nickname = session.get('nickname')
    if nickname and nickname in used_nicknames:
        if not is_admin():
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

    if text.startswith('/'):
        parts = text.split()
        cmd = parts[0].lower()

        # Herkes kullanabilir
        if cmd in ['/help', '/?']:
            commands = """
Komutlar:
/help veya /? - Komut listesini gösterir
/exit - Çıkış yapar
"""
            if is_admin():
                commands += """/reset - Sohbeti temizle (admin)
/mute [nickname] - Kullanıcıyı sustur (admin)
/unmute [nickname] - Susturmayı kaldır (admin)
/ip [nickname] - Kullanıcının IP adresini göster (admin)
/ban [nickname] - Kullanıcının IP'sini engelle (admin)
/unban [ip] - IP engelini kaldır (admin)
"""
            emit('receive_message', {'nickname': 'Sistem', 'text': commands})
            return

        elif cmd == '/exit':
            # Kullanıcı çıkış yapar, nickname serbest kalır
            if is_admin():
                # Admin çıkınca nickname kalır, sadece session temizlenir
                session.clear()
                disconnect()
            else:
                if nickname in used_nicknames:
                    used_nicknames.remove(nickname)
                session.clear()
                disconnect()
            return

        # Admin komutları
        if not is_admin():
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komutu kullanmak için admin olmalısınız.'})
            return

        if cmd == '/reset':
            messages.clear()
            emit('load_messages', messages, broadcast=True)
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Sohbet temizlendi!'}, broadcast=True)
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

        elif cmd == '/ip' and len(parts) == 2:
            target = parts[1]
            # Basit ip gösterme (Gerçek uygulamada ip'ler kayıtlı olmalı)
            # Örnek amaçlı burada gösterilemiyor.
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} kullanıcısının IP adresi sistemde kayıtlı değil.'})
            return

        elif cmd == '/ban' and len(parts) == 2:
            target = parts[1]
            # Ban için mesajlar içinde ip bulunabilir
            target_ip = None
            for msg in reversed(messages):
                if msg['nickname'] == target:
                    target_ip = msg.get('ip')
                    break
            if target_ip:
                banned_ips.add(target_ip)
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} IP {target_ip} engellendi.'}, broadcast=True)
            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} kullanıcısının IP'si bulunamadı.'})
            return

        elif cmd == '/unban' and len(parts) == 2:
            ip_to_unban = parts[1]
            if ip_to_unban in banned_ips:
                banned_ips.remove(ip_to_unban)
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{ip_to_unban} IP engeli kaldırıldı.'}, broadcast=True)
            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu IP engelli değil.'})
            return

        else:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Bilinmeyen komut. /help ile yardım alın.'})
            return

    # Normal mesaj
    msg = {'nickname': nickname, 'text': text, 'admin': is_admin(), 'ip': user_ip}
    messages.append(msg)
    emit('receive_message', msg, broadcast=True)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

