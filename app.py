from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, disconnect

app = Flask(__name__)
app.secret_key = 'gizli-anahtar'
socketio = SocketIO(app, manage_session=False)

messages = []
users_ip_mapping = {}  # nickname -> ip
banned_ips = set()
muted_nicks = set()
admins = set()

ADMIN_NICKNAME = "Admin"
ADMIN_PASSWORD = "9980"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        password = request.form.get('password', '')

        if not nickname:
            return render_template('nickname.html', error="Nickname boş olamaz.")

        # Admin nick kontrolü ve şifre doğrulama
        if nickname == ADMIN_NICKNAME:
            if password != ADMIN_PASSWORD:
                return render_template('nickname.html', error="Admin şifresi yanlış.")
            else:
                session['nickname'] = ADMIN_NICKNAME
                admins.add(ADMIN_NICKNAME)
                return redirect(url_for('chat'))

        # Normal nick kontrolü
        if nickname in [msg['nickname'] for msg in messages]:
            return render_template('nickname.html', error="Bu nickname zaten kullanılıyor.")

        session['nickname'] = nickname
        return redirect(url_for('chat'))

    # GET isteğinde nickname seçme ekranı
    if 'nickname' in session:
        return redirect(url_for('chat'))
    return render_template('nickname.html')

@app.route('/chat')
def chat():
    if 'nickname' not in session:
        return redirect(url_for('index'))
    return render_template('chat.html', nickname=session['nickname'])

@socketio.on('connect')
def on_connect():
    nickname = session.get('nickname')
    if not nickname:
        return False  # bağlantı reddedilir

    ip = request.remote_addr
    users_ip_mapping[nickname] = ip

    if ip in banned_ips:
        disconnect()
        return

    # Mesajları yollayalım yeni bağlanana
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
    if not text:
        return

    # Komutları ayrıştır
    if text.startswith('/'):
        # Komut listesi herkes için
        if text in ['/help', '/?']:
            komutlar = "/help, /?, /exit"
            if nickname in admins:
                komutlar += ", /ip <nick>, /ban <nick>, /mute <nick>, /unmute <nick>, /reset"
            emit('receive_message', {'nickname': 'Sistem', 'text': f'Komutlar: {komutlar}'})
            return

        # /exit komutu: nickname sil ve nickname seçme sayfasına at
        if text == '/exit':
            # Admin ise nickname silinmez, sadece socket bağlantısı kesilir
            if nickname == ADMIN_NICKNAME:
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{nickname} çıkış yaptı (admin nickname kalır).'}, broadcast=True)
                # Socket bağlantısını kes
                disconnect()
            else:
                # Mesaj listesinden kullanıcı mesajları silinir
                messages[:] = [m for m in messages if m['nickname'] != nickname]
                users_ip_mapping.pop(nickname, None)
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{nickname} çıkış yaptı.'}, broadcast=True)
                disconnect()

            # Session temizlenir
            session.pop('nickname', None)
            return

        # Diğer admin komutları sadece admin için
        if nickname != ADMIN_NICKNAME:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komutu sadece admin kullanabilir.'})
            return

        if text.startswith('/ip '):
            target = text[4:].strip()
            ip = users_ip_mapping.get(target)
            if ip:
                emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} kullanıcısının IP'si: {ip}"})
            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} bulunamadı."})
            return

        elif text.startswith('/ban '):
            target = text[5:].strip()
            ip = users_ip_mapping.get(target)
            if ip:
                banned_ips.add(ip)
                emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} IP adresi banlandı."}, broadcast=True)
                # Hedef bağlantısını kopar
                # Burada socket disconnect mekanizması genişletilebilir
            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} bulunamadı."})
            return

        elif text.startswith('/mute '):
            target = text[6:].strip()
            muted_nicks.add(target)
            emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} susturuldu."}, broadcast=True)
            return

        elif text.startswith('/unmute '):
            target = text[8:].strip()
            muted_nicks.discard(target)
            emit('receive_message', {'nickname': 'Sistem', 'text': f"{target} susturma kaldırıldı."}, broadcast=True)
            return

        elif text == '/reset':
            messages.clear()
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Sohbet sıfırlandı.'}, broadcast=True)
            return

        else:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Bilinmeyen komut.'})
            return

    # Normal mesaj
    msg = {'nickname': nickname, 'text': text}
    messages.append(msg)
    emit('receive_message', msg, broadcast=True)


if __name__ == '__main__':
    socketio.run(app, debug=True)

