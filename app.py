from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = 'gizli-anahtar'
socketio = SocketIO(app, manage_session=False)

messages = []
users_ip_mapping = {}  # nickname -> ip
banned_ips = set()
muted_nicks = set()
admins = set()

ADMIN_PASSWORD = "9980"

@app.route('/')
def index():
    if 'nickname' not in session:
        return render_template('nickname.html')
    return render_template('chat.html', nickname=session['nickname'])

@app.route('/set-nickname', methods=['POST'])
def set_nickname():
    nickname = request.form.get('nickname')
    if not nickname:
        return 'Eksik nickname', 400
    if nickname.lower() == 'admin' and request.form.get('password') != ADMIN_PASSWORD:
        return 'Hatalı şifre', 403
    if nickname in [msg['nickname'] for msg in messages]:
        return 'Nickname alınmış', 409

    session['nickname'] = nickname
    if nickname.lower() == 'admin':
        admins.add(session['nickname'])
    return '', 204

@socketio.on('connect')
def on_connect():
    nickname = session.get('nickname')
    if not nickname:
        return False  # Bağlantıyı reddet
    ip = request.remote_addr
    users_ip_mapping[nickname] = ip
    if ip in banned_ips:
        return False  # Banlıysa bağlantı kapansın
    emit('load_messages', messages)

@socketio.on('send_message')
def handle_message(data):
    nickname = session.get('nickname')
    if not nickname:
        return

    if nickname in muted_nicks:
        emit('receive_message', {'nickname': 'Sistem', 'text': 'Susturuldunuz, mesaj gönderemezsiniz.'})
        return

    text = data.get('text', '').strip()

    # Komut işlemleri
    if text.startswith('/'):
        if text in ['/help', '/?']:
            komutlar = "/help, /?, /exit"  # Herkes için
            if nickname in admins:
                komutlar += ", /ip <nick>, /ban <nick>, /mute <nick>, /unmute <nick>, /reset"
            emit('receive_message', {'nickname': 'Sistem', 'text': f'Komutlar: {komutlar}'})
            return

        elif text == '/exit':
            if nickname in admins:
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{nickname} çıkış yaptı (Admin, nickname silinmedi).'}, broadcast=True)
            else:
                messages[:] = [m for m in messages if m['nickname'] != nickname]
                users_ip_mapping.pop(nickname, None)
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{nickname} çıkış yaptı.'}, broadcast=True)
            session.pop('nickname', None)
            return

        elif text.startswith('/ip '):
            if nickname not in admins:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komutu sadece admin kullanabilir.'})
                return
            target = text[4:].strip()
            ip = users_ip_mapping.get(target)
            if ip:
                emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} kullanıcısının IP'si: {ip}"})
            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} bulunamadı."})
            return

        elif text.startswith('/ban '):
            if nickname not in admins:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komutu sadece admin kullanabilir.'})
                return
            target = text[5:].strip()
            ip = users_ip_mapping.get(target)
            if ip:
                banned_ips.add(ip)
                emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} IP adresi banlandı."}, broadcast=True)
            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} bulunamadı."})
            return

        elif text.startswith('/mute '):
            if nickname not in admins:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komutu sadece admin kullanabilir.'})
                return
            target = text[6:].strip()
            muted_nicks.add(target)
            emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} susturuldu."}, broadcast=True)
            return

        elif text.startswith('/unmute '):
            if nickname not in admins:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komutu sadece admin kullanabilir.'})
                return
            target = text[8:].strip()
            muted_nicks.discard(target)
            emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} susturma kaldırıldı."}, broadcast=True)
            return

        elif text == '/reset':
            if nickname not in admins:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komutu sadece admin kullanabilir.'})
                return
            messages.clear()
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Sohbet sıfırlandı.'}, broadcast=True)
            return

    # Normal mesaj
    msg = {'nickname': nickname, 'text': text}
    messages.append(msg)
    emit('receive_message', msg, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)

