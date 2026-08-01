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
