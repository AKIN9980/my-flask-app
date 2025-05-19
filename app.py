from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gizlisifre'
socketio = SocketIO(app)

messages = []          # Tüm mesajlar burada saklanacak
users = {}             # sid -> nickname
ips = {}               # sid -> ip
banned = set()         # yasaklı nickname'ler
muted = set()          # susturulan nickname'ler
ip_banned = set()      # yasaklı IP'ler

ADMIN_PASSWORD = "9980"

@app.route('/')
def nickname():
    return render_template('nickname.html')

@app.route('/admin_login')
def admin_login():
    return render_template('admin_login.html')

@app.route('/chat')
def chat():
    nickname = request.args.get('nickname')
    admin_flag = request.args.get('admin')
    password = request.args.get('password')

    if not nickname:
        return redirect(url_for('nickname'))

    if nickname.lower() == 'admin':
        if admin_flag != '1' or password != ADMIN_PASSWORD:
            return redirect(url_for('admin_login'))

    if nickname in banned or request.remote_addr in ip_banned:
        return "Yasaklısınız.", 403

    return render_template('chat.html', nickname=nickname, admin=(nickname.lower() == 'admin'))

@socketio.on('join')
def on_join(data):
    sid = request.sid
    nick = data.get('nickname')
    is_admin = data.get('isAdmin', False)

    if nick in banned or request.remote_addr in ip_banned:
        emit('message', {'msg': "Yasaklısınız, giriş engellendi.", 'admin': True})
        return

    users[sid] = nick
    ips[sid] = request.remote_addr

    # Eski mesajları gönder
    for msg in messages:
        emit('message', {'msg': msg, 'admin': False})

    msg = f"{nick} katıldı."
    messages.append(msg)
    emit('message', {'msg': msg, 'admin': False}, broadcast=True)

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
def handle_message(data):
    sid = request.sid
    nick = users.get(sid)
    msg_text = data.get('msg', '').strip()

    if not nick or nick in banned or ips.get(sid) in ip_banned:
        emit('message', {'msg': "Mesaj gönderme yetkiniz yok.", 'admin': True})
        return

    # Eğer susturulmuşsa mesaj gönderemez
    if nick in muted:
        emit('message', {'msg': "Susturuldunuz, mesaj gönderemezsiniz.", 'admin': True})
        return

    # Admin komutları
    if nick.lower() == 'admin' and msg_text.startswith('/'):
        cmd_parts = msg_text[1:].split()
        cmd = cmd_parts[0].lower()

        if cmd == 'reset':
            messages.clear()
            emit('message', {'msg': "Mesajlar sıfırlandı.", 'admin': True}, broadcast=True)

        elif cmd == 'ip' and len(cmd_parts) == 2:
            target = cmd_parts[1]
            target_ip = None
            for u_sid, u_nick in users.items():
                if u_nick == target:
                    target_ip = ips.get(u_sid)
                    break
            if target_ip:
                emit('message', {'msg': f"{target} IP'si: {target_ip}", 'admin': True})
            else:
                emit('message', {'msg': f"{target} aktif değil veya bulunamadı.", 'admin': True})

        elif cmd == 'ipban' and len(cmd_parts) == 2:
            target = cmd_parts[1]
            target_ip = None
            for u_sid, u_nick in users.items():
                if u_nick == target:
                    target_ip = ips.get(u_sid)
                    break
            if target_ip:
                ip_banned.add(target_ip)
                banned.add(target)
                emit('message', {'msg': f"{target} ve IP banlandı: {target_ip}", 'admin': True}, broadcast=True)
            else:
                banned.add(target)
                emit('message', {'msg': f"{target} banlandı (IP adresi bulunamadı).", 'admin': True}, broadcast=True)

        elif cmd == 'unipban' and len(cmd_parts) == 2:
            target = cmd_parts[1]
            target_ip = None
            for u_sid, u_nick in users.items():
                if u_nick == target:
                    target_ip = ips.get(u_sid)
                    break
            if target_ip and target_ip in ip_banned:
                ip_banned.discard(target_ip)
                banned.discard(target)
                emit('message', {'msg': f"{target} ve IP banı kaldırıldı.", 'admin': True}, broadcast=True)
            else:
                banned.discard(target)
                emit('message', {'msg': f"{target} banı kaldırıldı (IP adresi bulunamadı veya banlı değil).", 'admin': True}, broadcast=True)

        elif cmd == 'mute' and len(cmd_parts) == 2:
            target = cmd_parts[1]
            muted.add(target)
            emit('message', {'msg': f"{target} susturuldu.", 'admin': True}, broadcast=True)

        elif cmd == 'unmute' and len(cmd_parts) == 2:
            target = cmd_parts[1]
            muted.discard(target)
            emit('message', {'msg': f"{target} susturulması kaldırıldı.", 'admin': True}, broadcast=True)

        elif cmd == 'exit':
            emit('message', {'msg': "Admin çıkış yaptı.", 'admin': True}, broadcast=True)
            disconnect(sid)

        else:
            emit('message', {'msg': "Bilinmeyen admin komutu.", 'admin': True})

        return

    # Kullanıcı komutları
    if msg_text.startswith('/'):
        cmd = msg_text[1:].lower()
        if cmd in ['?', 'help']:
            help_msg = (
                "Kullanıcı komutları:\n"
                "/? veya /help - Yardım\n"
                "/exit - Çıkış"
            )
            emit('message', {'msg': help_msg, 'admin': True})
        elif cmd == 'exit':
            emit('message', {'msg': f"{nick} sohbetten çıktı.", 'admin': False}, broadcast=True)
            disconnect(sid)
        else:
            emit('message', {'msg': "Bilinmeyen komut.", 'admin': True})
        return

    # Normal mesaj
    full_msg = f"{nick}: {msg_text}"
    messages.append(full_msg)
    emit('message', {'msg': full_msg, 'admin': False}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

