from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
from flask_session import Session

app = Flask(__name__)
app.secret_key = 'gizli-anahtar'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
socketio = SocketIO(app, manage_session=False)

messages = []

@app.route('/')
def index():
    if 'nickname' not in session:
        return render_template('nickname.html')
    return render_template('chat.html', nickname=session['nickname'])

@app.route('/set-nickname', methods=['POST'])
def set_nickname():
    nickname = request.form.get('nickname')
    if nickname:
        session['nickname'] = nickname
        return ('', 204)
    return ('Bad Request', 400)

@socketio.on('connect')
def on_connect():
    emit('load_messages', messages)

@socketio.on('send_message')
def handle_message(data):
    msg = {
        'nickname': session.get('nickname', 'Anonim'),
        'text': data['text']
    }
    messages.append(msg)
    emit('receive_message', msg, broadcast=True)

if __name__ == '__main__':
    socketio.run(app)

