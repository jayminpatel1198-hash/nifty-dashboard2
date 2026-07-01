from flask import Flask, render_template_string, jsonify
import requests, gzip, json, time, math
import pandas as pd
import numpy as np

ACCESS_TOKEN = "PASTE_YOUR_UPSTOX_ACCESS_TOKEN_HERE"

REFRESH_SECONDS = 20
INTERVAL = "5minute"

NIFTY50 = [
    "RELIANCE","HDFCBANK","ICICIBANK","INFY","TCS","LT","SBIN","BHARTIARTL","AXISBANK","KOTAKBANK",
    "ITC","HINDUNILVR","BAJFINANCE","ASIANPAINT","MARUTI","SUNPHARMA","TITAN","ULTRACEMCO","NESTLEIND","M&M",
    "HCLTECH","TATAMOTORS","NTPC","POWERGRID","ONGC","ADANIENT","ADANIPORTS","COALINDIA","BAJAJFINSV","WIPRO",
    "JSWSTEEL","TATASTEEL","TECHM","GRASIM","HINDALCO","CIPLA","DRREDDY","DIVISLAB","BRITANNIA","EICHERMOT",
    "HEROMOTOCO","APOLLOHOSP","BPCL","BAJAJ-AUTO","UPL","LTIM","SBILIFE","HDFCLIFE","INDUSINDBK","TATACONSUM"
]

WEIGHTS = {
    "RELIANCE":9.47,"HDFCBANK":6.19,"BHARTIARTL":5.93,"SBIN":4.78,"ICICIBANK":4.75,"TCS":4.32,
    "INFY":3.10,"LT":3.80,"KOTAKBANK":2.50,"AXISBANK":2.80,"ITC":2.70,"HINDUNILVR":2.00,
    "BAJFINANCE":2.00,"SUNPHARMA":1.80,"MARUTI":1.50,"M&M":1.60,"TITAN":1.40,"NTPC":1.40,
    "POWERGRID":1.20,"ONGC":1.10
}

app = Flask(__name__)
cache = {"time":0, "data":[], "summary":{}}

def upstox_headers():
    return {"Accept":"application/json", "Authorization":f"Bearer {ACCESS_TOKEN}"}

def load_instrument_keys():
    url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
    r = requests.get(url, timeout=20)
    raw = gzip.decompress(r.content)
    data = json.loads(raw.decode("utf-8"))
    mp = {}
    for x in data:
        if x.get("segment") == "NSE_EQ" and x.get("instrument_type") == "EQ":
            ts = x.get("trading_symbol")
            if ts in NIFTY50:
                mp[ts] = x.get("instrument_key")
    return mp

INSTRUMENTS = load_instrument_keys()

def get_candles(instrument_key):
    url = f"https://api.upstox.com/v2/historical-candle/intraday/{instrument_key}/{INTERVAL}"
    r = requests.get(url, headers=upstox_headers(), timeout=10)
    js = r.json()
    candles = js.get("data", {}).get("candles", [])
    if not candles:
        return None
    df = pd.DataFrame(candles, columns=["time","open","high","low","close","volume","oi"])
    df = df.iloc[::-1].reset_index(drop=True)
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def adx(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)
    tr = pd.concat([(high-low), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * pd.Series(plus_dm).rolling(period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).rolling(period).mean() / atr
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    return dx.rolling(period).mean()

def analyze(symbol, key):
    df = get_candles(key)
    if df is None or len(df) < 35:
        return {"symbol":symbol, "signal":"NO DATA", "score":0}

    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["rsi"] = rsi(df["close"], 14)
    df["adx"] = adx(df, 14)
    df["vol_avg"] = df["volume"].rolling(20).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(last["close"])
    change = ((price - float(df.iloc[0]["open"])) / float(df.iloc[0]["open"])) * 100

    score = 0
    reasons = []

    if last["ema9"] > last["ema21"]:
        score += 25; reasons.append("EMA Bullish")
    else:
        score -= 25; reasons.append("EMA Bearish")

    if last["rsi"] > 55:
        score += 20; reasons.append("RSI Strong")
    elif last["rsi"] < 45:
        score -= 20; reasons.append("RSI Weak")

    if last["adx"] > 20:
        score += 15 if last["ema9"] > last["ema21"] else -15
        reasons.append("ADX Trend")

    if last["volume"] > last["vol_avg"]:
        score += 10 if change > 0 else -10
        reasons.append("Volume Confirm")

    if last["close"] > prev["high"]:
        score += 15; reasons.append("Breakout")
    elif last["close"] < prev["low"]:
        score -= 15; reasons.append("Breakdown")

    if score >= 45:
        signal = "BUY"
    elif score <= -45:
        signal = "SELL"
    else:
        signal = "WAIT"

    return {
        "symbol": symbol,
        "price": round(price,2),
        "change": round(change,2),
        "ema9": round(float(last["ema9"]),2),
        "ema21": round(float(last["ema21"]),2),
        "rsi": round(float(last["rsi"]),2) if not math.isnan(last["rsi"]) else 0,
        "adx": round(float(last["adx"]),2) if not math.isnan(last["adx"]) else 0,
        "volume": int(last["volume"]),
        "signal": signal,
        "score": int(score),
        "weight": WEIGHTS.get(symbol,0.50),
        "reason": ", ".join(reasons)
    }

def build_dashboard():
    rows = []
    for symbol in NIFTY50:
        key = INSTRUMENTS.get(symbol)
        if not key:
            rows.append({"symbol":symbol, "signal":"KEY MISSING", "score":0, "weight":0})
            continue
        try:
            rows.append(analyze(symbol, key))
        except Exception as e:
            rows.append({"symbol":symbol, "signal":"ERROR", "score":0, "weight":0, "reason":str(e)[:80]})

    bull_w = sum(r.get("weight",0) for r in rows if r.get("signal")=="BUY")
    bear_w = sum(r.get("weight",0) for r in rows if r.get("signal")=="SELL")
    buy_count = sum(1 for r in rows if r.get("signal")=="BUY")
    sell_count = sum(1 for r in rows if r.get("signal")=="SELL")

    if bull_w > bear_w + 5:
        market = "BULLISH"
    elif bear_w > bull_w + 5:
        market = "BEARISH"
    else:
        market = "SIDEWAYS"

    summary = {
        "market": market,
        "bull_w": round(bull_w,2),
        "bear_w": round(bear_w,2),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "wait_count": 50-buy_count-sell_count
    }
    return rows, summary

@app.route("/api")
def api():
    now = time.time()
    if now - cache["time"] > REFRESH_SECONDS:
        cache["data"], cache["summary"] = build_dashboard()
        cache["time"] = now
    return jsonify({"rows":cache["data"], "summary":cache["summary"], "updated":time.strftime("%H:%M:%S")})

HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty 50 Lawrence Style Dashboard</title>
<style>
body{font-family:Arial;background:#0b1020;color:white;margin:0;padding:12px}
.card{background:#151b2f;border-radius:14px;padding:14px;margin-bottom:12px}
h2{margin:0 0 8px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.box{background:#202842;border-radius:10px;padding:10px;text-align:center}
table{width:100%;border-collapse:collapse;background:#151b2f;border-radius:12px;overflow:hidden}
th,td{padding:8px;border-bottom:1px solid #29324f;font-size:13px;text-align:center}
th{background:#202842;position:sticky;top:0}
.buy{color:#00ff99;font-weight:bold}
.sell{color:#ff5c5c;font-weight:bold}
.wait{color:#ffd166;font-weight:bold}
.err{color:#aaa}
.pos{color:#00ff99}.neg{color:#ff5c5c}
</style>
</head>
<body>
<div class="card">
<h2>Nifty 50 Lawrence Style Dashboard</h2>
<div id="updated"></div>
<div class="grid">
<div class="box"><b>Market</b><br><span id="market"></span></div>
<div class="box"><b>Bull Weight</b><br><span id="bull"></span></div>
<div class="box"><b>Bear Weight</b><br><span id="bear"></span></div>
</div>
</div>

<table>
<thead>
<tr>
<th>Stock</th><th>Price</th><th>%</th><th>EMA9</th><th>EMA21</th><th>RSI</th><th>ADX</th><th>Signal</th><th>Score</th><th>Reason</th>
</tr>
</thead>
<tbody id="rows"></tbody>
</table>

<script>
async function load(){
 let r = await fetch('/api');
 let d = await r.json();
 document.getElementById("updated").innerHTML = "Updated: " + d.updated;
 document.getElementById("market").innerHTML = d.summary.market;
 document.getElementById("bull").innerHTML = d.summary.bull_w + " | Buy: " + d.summary.buy_count;
 document.getElementById("bear").innerHTML = d.summary.bear_w + " | Sell: " + d.summary.sell_count;

 let html = "";
 d.rows.sort((a,b)=>Math.abs(b.score||0)-Math.abs(a.score||0));
 for(let x of d.rows){
   let cls = x.signal=="BUY"?"buy":x.signal=="SELL"?"sell":x.signal=="WAIT"?"wait":"err";
   let chcls = (x.change||0)>=0 ? "pos":"neg";
   html += `<tr>
   <td><b>${x.symbol}</b></td>
   <td>${x.price||"-"}</td>
   <td class="${chcls}">${x.change||0}</td>
   <td>${x.ema9||"-"}</td>
   <td>${x.ema21||"-"}</td>
   <td>${x.rsi||"-"}</td>
   <td>${x.adx||"-"}</td>
   <td class="${cls}">${x.signal}</td>
   <td>${x.score||0}</td>
   <td>${x.reason||""}</td>
   </tr>`;
 }
 document.getElementById("rows").innerHTML = html;
}
load();
setInterval(load, 20000);
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    print("Open: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
