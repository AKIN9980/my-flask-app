from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO, emit, disconnect
import re

app = Flask(__name__)
socketio = SocketIO(app)

messages = []
users = {}
banned_ips = set()
muted_users = set()

ADMIN_NICKNAME = 'Admin'
ADMIN_PASSWORD = '9980'

@app.route('/')
def index():
    return render_template('nickname.html')

@app.route('/chat')
def chat():
    nickname = request.args.get('nickname')
    if not nickname:
        return redirect('/')
    return render_template('chat.html', nickname=nickname)

@socketio.on('connect')
def handle_connect():
    ip = request.remote_addr
    if ip in banned_ips:
        disconnect()
        return
    emit('load_messages', messages)

@socketio.on('send_message')
def handle_message(data):
    ip = request.remote_addr
    nickname = users.get(request.sid)
    if ip in banned_ips:
        return
    if nickname in muted_users:
        return

    text = data.get('text', '').strip()
    if not text:
        return

    # Komut işlemleri
    if text.startswith('/'):
        if text.lower() in ['/help', '/?']:
            help_text = (
                'Komutlar:\n'
                '/help veya /? - Yardım\n'
                '/exit - Çıkış yap\n'
            )
            if nickname == ADMIN_NICKNAME:
                help_text += (
                    '/reset - Sohbeti temizle\n'
                    '/ban <ip> - IP banla\n'
                    '/mute <nickname> - Sustur\n'
                    '/unmute <nickname> - Susturmayı kaldır\n'
                    '/ip <nickname> - IP öğren\n'
                )
            emit('receive_message', {'nickname': 'Sistem', 'text': help_text})
            return

        if text.lower() == '/exit':
            if nickname:
                users.pop(request.sid, None)
                emit('receive_message', {'nickname': 'Sistem', 'text': f'{nickname} çıktı.'}, broadcast=True)
                disconnect()
            return

        if nickname != ADMIN_NICKNAME:
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Bu komut sadece admin için geçerlidir.'})
            return

        # Admin komutları:
        parts = text.split()
        cmd = parts[0].lower()

        if cmd == '/reset':
            messages.clear()
            emit('load_messages', [], broadcast=True)
            emit('receive_message', {'nickname': 'Sistem', 'text': 'Sohbet temizlendi (Admin tarafından).'}, broadcast=True)
            return

        if cmd == '/ban' and len(parts) == 2:
            banned_ips.add(parts[1])
            emit('receive_message', {'nickname': 'Sistem', 'text': f'IP {parts[1]} banlandı.'}, broadcast=True)
            return

        if cmd == '/mute' and len(parts) == 2:
            muted_users.add(parts[1])
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{parts[1]} susturuldu.'}, broadcast=True)
            return

        if cmd == '/unmute' and len(parts) == 2:
            muted_users.discard(parts[1])
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{parts[1]} susturma kaldırıldı.'}, broadcast=True)
            return

        if cmd == '/ip' and len(parts) == 2:
            target = parts[1]
            for sid, nick in users.items():
                if nick == target:
                    # ip bilgisi yok socket'te, normal şartlarda loglanır veya request ip kullanılır
                    emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} IP adresi: ???'}, room=request.sid)
                    return
            emit('receive_message', {'nickname': 'Sistem', 'text': f'{target} bulunamadı.'}, room=request.sid)
            return

    # Normal mesaj
    messages.append({'nickname': nickname, 'text': text})
    # mesajları 100 ile sınırla (isteğe göre)
    if len(messages) > 100:
        messages.pop(0)
    emit('receive_message', {'nickname': nickname, 'text': text}, broadcast=True)

@socketio.on('set_nickname')
def set_nickname(nick):
    users[request.sid] = nick
    emit('receive_message', {'nickname': 'Sistem', 'text': f'{nick} sohbete katıldı.'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    nick = users.pop(request.sid, None)
    if nick:
        emit('disconnect_message', f'{nick} çıktı.', broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

