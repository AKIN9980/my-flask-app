from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
import uuid

app = Flask(__name__)
app.secret_key = 'anonchat_secret'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
CORS(app)

messages = []

@app.route('/')
def index():
    if 'nickname' not in session:
        session['nickname'] = f"anon-{uuid.uuid4().hex[:6]}"
    return render_template('index.html', nickname=session['nickname'])

@app.route('/send', methods=['POST'])
def send():
    data = request.json
    nickname = session.get('nickname', 'anon')
    msg = data.get('message', '').strip()
    if msg:
        messages.append({"nick": nickname, "msg": msg})
    return jsonify(success=True)

@app.route('/messages')
def get_messages():
    return jsonify(messages)

if __name__ == '__main__':
    app.run(debug=True)

--- requirements.txt ---
flask
flask-cors
flask-session
