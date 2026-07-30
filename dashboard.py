from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Dashboard V2 Loading..."

if __name__ == "__main__":
    app.run()
