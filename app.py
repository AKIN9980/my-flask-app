from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.secret_key = 'çok-gizli-bir-anahtar'
socketio = SocketIO(app, async_mode='eventlet')

nicknames = set()
messages = []
banned = set()
admin_password = "9980"  # Dilediğin gibi değiştir

def is_admin():
    return session.get('is_admin', False)

@app.route('/', methods=['GET', 'POST'])
def nickname():
    if request.method == 'POST':
        nick = request.form.get('nickname', '').strip()
        password = request.form.get('password', '').strip()

        if not nick:
            return render_template('nickname.html', error="Lütfen nickname girin.")

        if nick in banned:
            return render_template('nickname.html', error="Bu kullanıcı engellenmiştir.")

        if nick == "Admin":
            if password != admin_password:
                return render_template('nickname.html', error="Admin şifresi yanlış.")
            session['is_admin'] = True
        else:
            session['is_admin'] = False

        if nick in nicknames:
            return render_template('nickname.html', error="Bu nickname zaten kullanılıyor.")

        nicknames.add(nick)
        session['nickname'] = nick
        return redirect(url_for('chat'))

    return render_template('nickname.html')

@app.route('/chat')
def chat():
    if 'nickname' not in session:
        return redirect(url_for('nickname'))
    return render_template('chat.html', nickname=session['nickname'], is_admin=is_admin(), messages=messages)

@socketio.on('send_message')
def handle_message(data):
    text = data.get('text', '').strip()
    nick = session.get('nickname')
    if not nick or not text:
        return

    if text.startswith('/'):
        # Yardım komutları
        if text in ['/help', '/?']:
            help_text = (
                "Komutlar:\n"
                "/help, /? - Yardım\n"
                "/exit - Çıkış yap\n"
                "Admin Komutları:\n"
                "/reset - Sohbeti temizle\n"
                "/ip <nick> - Kullanıcının IP'sini göster\n"
                "/kick <nick> - Kullanıcıyı at\n"
                "/ban <nick> - Kullanıcıyı engelle\n"
                "/unban <nick> - Engel kaldır\n"
                "/list - Aktif kullanıcılar"
            )
            emit('receive_message', {'nickname': 'Sistem', 'text': help_text}, room=request.sid)
            return

        if text == '/exit':
            nicknames.discard(nick)
            session.pop('nickname', None)
            session.pop('is_admin', None)
            emit('exit_chat', room=request.sid)
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{nick} sohbetten çıktı.'}, broadcast=True)
            return

        if not is_admin():
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komutu kullanmak için admin olmalısınız.'}, room=request.sid)
            return

        # Admin komutları
        parts = text.split(' ', 1)
        command = parts[0]
        param = parts[1].strip() if len(parts) > 1 else None

        if command == '/reset':
            messages.clear()
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Sohbet sıfırlandı!'}, broadcast=True)
            return

        if command == '/ip':
            if not param:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Kullanıcı adı belirtmelisin!'}, room=request.sid)
                return
            if param in nicknames:
                # IP bilgisi tutulmuyorsa sabit örnek veriyoruz
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{param} IP: 127.0.0.1 (demo)'}, room=request.sid)
            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{param} bulunamadı.'}, room=request.sid)
            return

        if command == '/kick':
            if not param:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Kullanıcı adı belirtmelisin!'}, room=request.sid)
                return
            if param in nicknames:
                nicknames.discard(param)
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{param} sohbetten atıldı.'}, broadcast=True)
                # Kicklenen kullanıcıyı sayfadan at (emit gönder)
                emit('exit_chat', room=request.sid, include_self=False)
            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{param} bulunamadı.'}, room=request.sid)
            return

        if command == '/ban':
            if not param:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Kullanıcı adı belirtmelisin!'}, room=request.sid)
                return
            banned.add(param)
            if param in nicknames:
                nicknames.discard(param)
                emit('exit_chat', room=request.sid, include_self=False)
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{param} engellendi.'}, broadcast=True)
            return

        if command == '/unban':
            if not param:
                emit('receive_message', {'nickname': 'Sistem', 'text': 'Kullanıcı adı belirtmelisin!'}, room=request.sid)
                return
            if param in banned:
                banned.discard(param)
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{param} engeli kaldırıldı.'}, room=request.sid)
            else:
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{param} engelli değil.'}, room=request.sid)
            return

        if command == '/list':
            aktifler = ', '.join(nicknames)
            emit('receive_message', {'nickname': 'Sistem', 'text': f'Aktif kullanıcılar: {aktifler}'}, room=request.sid)
            return

        emit('receive_message', {'nickname': 'Sistem', 'text': 'Bilinmeyen komut!'}, room=request.sid)
        return

    # Normal mesaj kaydet ve yayınla
    msg_obj = {'nickname': nick, 'text': text}
    messages.append(msg_obj)
    emit('receive_message', msg_obj, broadcast=True)

@socketio.on('disconnect')
def on_disconnect():
    nick = session.get('nickname')
    if nick and nick in nicknames:
        nicknames.discard(nick)
        emit('receive_message', {'nickname': 'Sistem', 'text': f'{nick} ayrıldı.'}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)

