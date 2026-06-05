
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>Nifty Dashboard 2 Running</h1>"
