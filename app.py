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
