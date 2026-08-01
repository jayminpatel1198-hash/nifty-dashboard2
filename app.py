from flask import Flask, jsonify, render_template
import os
import requests

app = Flask(__name__)

TOKEN = os.environ.get("UPSTOX_TOKEN", "").strip()

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}

INDEX_KEY = "NSE_INDEX|Nifty 50"

QUOTE_URL = "https://api.upstox.com/v2/market-quote/quotes"
OPTION_CHAIN_URL = "https://api.upstox.com/v2/option/chain"
CONTRACT_URL = "https://api.upstox.com/v2/option/contract"

STEP = 50
def get_json(url, params=None):
    r = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=10
    )

    r.raise_for_status()
    return r.json()


def num(x):
    try:
        return float(x)
    except:
        return 0.0


def get_spot():
    data = get_json(
        QUOTE_URL,
        {
            "instrument_key": INDEX_KEY
        }
    )

    quotes = data.get("data", {})
    info = quotes.get(INDEX_KEY, {})

    ltp = num(info.get("last_price"))

    if ltp == 0:
        ltp = num(info.get("ltp"))

    if ltp == 0:
        ohlc = info.get("ohlc", {})
        ltp = num(ohlc.get("close"))

    return ltp
    def get_expiry():
    data = get_json(
        CONTRACT_URL,
        {
            "instrument_key": INDEX_KEY
        }
    )

    print(data)

    contracts = data.get("data", [])

    if not contracts:
        return None

    for c in contracts:
        if "expiry" in c:
            return c["expiry"]

        if "expiry_date" in c:
            return c["expiry_date"]

    return None

def atm_strike(spot):
    return int(round(spot / STEP) * STEP)


def get_option_chain(expiry):
    return get_json(
        OPTION_CHAIN_URL,
        {
            "instrument_key": INDEX_KEY,
            "expiry_date": expiry
        }
    )
    @app.route("/api")
def api():

    spot = get_spot()

    expiry = get_expiry()

    if not expiry:
        return jsonify({
            "error": "No expiry found"
        })

    atm = atm_strike(spot)

    chain = get_option_chain(expiry)

    return jsonify({
        "spot": spot,
        "atm": atm,
        "expiry": expiry,
        "chain": chain
    })

@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
