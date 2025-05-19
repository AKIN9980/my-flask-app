from flask import Flask, render_template, request, make_response
from flask_socketio import SocketIO, emit
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# Ana sayfa
@app.route('/')
def index():
    nickname = request.cookies.get('nickname')
    if not nickname:
        nickname = str(uuid.uuid4())[:8]  # Rastgele 8 karakterlik nick
        resp = make_response(render_template('index.html', nickname=nickname))
        resp.set_cookie('nickname', nickname)
        return resp
    return render_template('index.html', nickname=nickname)

# Yeni mesaj geldiğinde
@socketio.on('chat message')
def handle_message(data):
    emit('chat message', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app)

