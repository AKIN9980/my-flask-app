from flask import Flask, render_template_string
import random

app = Flask(__name__)

messages = [
    "YOU ARE IDIOT!",
    "SORRY, NO INTELLIGENCE DETECTED.",
    "TRY AGAIN, GENIUS.",
    "ERROR 404: SMARTNESS NOT FOUND.",
    "DON'T TAKE IT PERSONALLY!"
]

@app.route('/')
def home():
    message = random.choice(messages)
    return render_template_string('''
    <html>
    <head>
      <title>youareidiot</title>
      <style>
        body {
          background-color: black;
          color: red;
          font-family: 'Arial Black', Arial, sans-serif;
          display: flex;
          justify-content: center;
          align-items: center;
          height: 100vh;
          margin: 0;
          font-size: 5em;
          user-select: none;
        }
      </style>
    </head>
    <body>
      {{ message }}
    </body>
    </html>
    ''', message=message)

if __name__ == '__main__':
    app.run(debug=True)
