from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, disconnect

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

    if nickname in banned:
        return "Yasaklısınız.", 403

    return render_template('chat.html', nickname=nickname, admin=(nickname.lower() == 'admin'))

@socketio.on('join')
def on_join(data):
    sid = request.sid
    nick = data.get('nickname')
    is_admin = data.get('isAdmin', False)

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

@socketio.on

