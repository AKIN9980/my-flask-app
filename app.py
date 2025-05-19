from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gizlisifre'
socketio = SocketIO(app)

messages = []
users = {}  # sid -> nickname
banned = set()
muted = set()
ips = {}  # sid -> ip

ADMIN_PASSWORD = "9980"

@app.route('/')
def nickname():
    return render_template('nickname.html')

@app.route('/chat')
def chat():
    nickname = request.args.get('nickname')
    admin_flag = request.args.get('admin')
    password = request.args.get('password')

    if not nickname:
        return redirect(url_for('nickname'))

    if nickname.lower() == 'admin':
        if admin_flag != '1' or password != ADMIN_PASSWORD:
            return redirect(url_for('nickname'))

    if nickname in banned:
        return "Yasaklısınız.", 403

    return render_template('chat.html', nickname=nickname, admin=(nickname.lower() == 'admin'))

@socketio.on('join')
def on_join(data):
    sid = request.sid
    nick = data.get('nickname')
    users[sid] = nick
    ips[sid] = request.remote_addr

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
    # Sesli chat peer bağlantılarını kaldır
    emit('voice-user-left', {'sid': sid}, broadcast=True, include_self=False)

# --- SESLİ CHAT EKLEMELERİ ---

@socketio.on('voice-on')
def handle_voice_on():
    sid = request.sid
    emit('voice-user-joined', {'sid': sid}, broadcast=True, include_self=False)

@socketio.on('voice-off')
def handle_voice_off():
    sid = request.sid
    emit('voice-user-left', {'sid': sid}, broadcast=True, include_self=False)

@socketio.on('voice-offer')
def handle_voice_offer(data):
    to = data.get('to')
    offer = data.get('offer')
    from_sid = request.sid
    emit('voice-offer', {'from': from_sid, 'offer': offer}, to=to)

@socketio.on('voice-answer')
def handle_voice_answer(data):
    to = data.get('to')
    answer = data.get('answer')
    from_sid = request.sid
    emit('voice-answer', {'from': from_sid, 'answer': answer}, to=to)

@socketio.on('voice-candidate')
def handle_voice_candidate(data):
    to = data.get('to')
    candidate = data.get('candidate')
    from_sid = request.sid
    emit('voice-candidate', {'from': from_sid, 'candidate': candidate}, to=to)

if __name__ == '__main__':
    socketio.run(app, debug=True)

