from flask import Flask, render_template_string
from markupsafe import Markup
import requests
import os
from datetime import datetime

app = Flask(__name__)
TOKEN = os.environ.get("UPSTOX_TOKEN")

stocks = {
"RELIANCE":"NSE_EQ|INE002A01018","HDFCBANK":"NSE_EQ|INE040A01034","BHARTIARTL":"NSE_EQ|INE397D01024",
"SBIN":"NSE_EQ|INE062A01020","ICICIBANK":"NSE_EQ|INE090A01021","TCS":"NSE_EQ|INE467B01029",
"BAJFINANCE":"NSE_EQ|INE296A01032","LT":"NSE_EQ|INE018A01030","INFY":"NSE_EQ|INE009A01021",
"HINDUNILVR":"NSE_EQ|INE030A01027","SUNPHARMA":"NSE_EQ|INE044A01036","ADANIPORTS":"NSE_EQ|INE742F01042",
"MARUTI":"NSE_EQ|INE585B01010","AXISBANK":"NSE_EQ|INE238A01034","ADANIENT":"NSE_EQ|INE423A01024",
"KOTAKBANK":"NSE_EQ|INE237A01036","M&M":"NSE_EQ|INE101A01026","TITAN":"NSE_EQ|INE280A01028",
"NTPC":"NSE_EQ|INE733E01010","ITC":"NSE_EQ|INE154A01025","ONGC":"NSE_EQ|INE213A01029",
"ULTRACEMCO":"NSE_EQ|INE481G01011","JSWSTEEL":"NSE_EQ|INE019A01038","HCLTECH":"NSE_EQ|INE860A01027",
"BEL":"NSE_EQ|INE263A01024","COALINDIA":"NSE_EQ|INE522F01014","BAJAJ-AUTO":"NSE_EQ|INE917I01010",
"BAJAJFINSV":"NSE_EQ|INE918I01026","POWERGRID":"NSE_EQ|INE752E01010","TATASTEEL":"NSE_EQ|INE081A01020",
"HINDALCO":"NSE_EQ|INE038A01020","ASIANPAINT":"NSE_EQ|INE021A01026","ETERNAL":"NSE_EQ|INE758T01015",
"SHRIRAMFIN":"NSE_EQ|INE721A01047","WIPRO":"NSE_EQ|INE075A01022","GRASIM":"NSE_EQ|INE047A01021",
"EICHERMOT":"NSE_EQ|INE066A01021","SBILIFE":"NSE_EQ|INE123W01016","JIOFIN":"NSE_EQ|INE758E01017",
"TRENT":"NSE_EQ|INE849A01020","HDFCLIFE":"NSE_EQ|INE795G01014","APOLLOHOSP":"NSE_EQ|INE437A01024",
"TATACONSUM":"NSE_EQ|INE192A01025","CIPLA":"NSE_EQ|INE059A01026","NESTLEIND":"NSE_EQ|INE239A01024",
"DRREDDY":"NSE_EQ|INE089A01031","TECHM":"NSE_EQ|INE669C01036","INDUSINDBK":"NSE_EQ|INE095A01012",
"HEROMOTOCO":"NSE_EQ|INE158A01026"
}

weights = {
"RELIANCE":9.47,"HDFCBANK":6.19,"BHARTIARTL":5.93,"SBIN":4.78,
"ICICIBANK":4.75,"TCS":4.32,"BAJFINANCE":2.91,"LT":2.90,
"INFY":2.64,"HINDUNILVR":2.62,"SUNPHARMA":2.29,"ADANIPORTS":2.21,
"MARUTI":2.19,"AXISBANK":2.08,"ADANIENT":2.03,"KOTAKBANK":2.02,
"M&M":2.00,"TITAN":1.93,"NTPC":1.90,"ITC":1.85
}

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>Nifty Option Dashboard</title>
<style>
body {font-family:Arial;background:#f4f6f8;padding:14px;margin:0}
.card {background:white;padding:15px;margin:10px;border-radius:12px;box-shadow:0 2px 5px #ddd}
.signal {padding:18px;border-radius:14px;text-align:center;font-size:23px;font-weight:bold;margin:10px}
.big {font-size:25px;font-weight:bold}
.green {color:green;font-weight:bold}
.red {color:red;font-weight:bold}
table {width:100%;border-collapse:collapse}
td,th {padding:8px;border-bottom:1px solid #ddd;text-align:left}
</style>
</head>
<body>
<h2 style="text-align:center">NIFTY OPTION DASHBOARD</h2>

<div class="signal" style="background:{{ color }}">{{ signal }}</div>

<div class="card">Green: <span class="big green">{{ green }} ({{ green_pct }}%)</span></div>
<div class="card">Red: <span class="big red">{{ red }} ({{ red_pct }}%)</span></div>
<div class="card">Flat: <span class="big">{{ flat }}</span></div>
<div class="card">Bull Score: <span class="big">{{ bull_score }}/100</span></div>
<div class="card">Put Score: <span class="big">{{ put_score }}/100</span></div>
<div class="card">Market Mood: <span class="big">{{ mood }}</span></div>
<div class="card">Risk: <span class="big">{{ risk }}</span></div>
<div class="card">Strength: <span class="big">{{ strength }}</span></div>
<div class="card">Weight Score: <span class="big">{{ weight_score }}</span></div>

<div class="card">
<h3>Top 5 Gainers</h3>
<table><tr><th>Stock</th><th>Price</th><th>%</th></tr>{{ gainers }}</table>
</div>

<div class="card">
<h3>Top 5 Losers</h3>
<table><tr><th>Stock</th><th>Price</th><th>%</th></tr>{{ losers }}</table>
</div>

<p style="text-align:center">Updated: {{ time }}</p>
</body>
</html>
"""

def make_table(items):
    out = ""
    for r in items:
        cls = "green" if r["pct"] > 0 else "red"
        out += f"<tr><td>{r['symbol']}</td><td>{r['price']}</td><td class='{cls}'>{r['pct']}%</td></tr>"
    return Markup(out)

@app.route("/")
def home():
    if not TOKEN:
        return "UPSTOX_TOKEN missing in Render Environment"

    headers = {"Accept": "application/json", "Authorization": "Bearer " + TOKEN}
    keys = ",".join(stocks.values())

    try:
        res = requests.get(
            "https://api.upstox.com/v2/market-quote/quotes",
            headers=headers,
            params={"instrument_key": keys},
            timeout=15
        )
        data = res.json()["data"]
    except Exception as e:
        return "Upstox API Error: " + str(e)

    green = red = flat = 0
    weight_score = 0
    rows = []

    for s in data.values():
        symbol = s.get("symbol", "")
        price = s.get("last_price", 0)
        close = s.get("ohlc", {}).get("close", 0)
        change = s.get("net_change", 0)
        pct = round((change / close) * 100, 2) if close else 0

        if change > 0:
            green += 1
            weight_score += weights.get(symbol, 0)
        elif change < 0:
            red += 1
            weight_score -= weights.get(symbol, 0)
        else:
            flat += 1

        rows.append({"symbol": symbol, "price": price, "pct": pct})

    total = green + red + flat
    green_pct = round(green * 100 / total, 1) if total else 0
    red_pct = round(red * 100 / total, 1) if total else 0

    bull_score = max(0, min(100, round(50 + weight_score, 1)))
    put_score = round(100 - bull_score, 1)

    if green_pct >= 65 and bull_score >= 70:
        signal = "STRONG CALL BIAS"
        mood = "TRENDING BULLISH"
        risk = "LOW"
        strength = "STRONG"
        color = "#d9fbe6"
    elif red_pct >= 65 and bull_score <= 30:
        signal = "STRONG PUT BIAS"
        mood = "TRENDING BEARISH"
        risk = "LOW"
        strength = "STRONG"
        color = "#ffe1e1"
    elif 45 <= green_pct <= 55:
        signal = "NO TRADE - SIDEWAYS"
        mood = "CHOPPY"
        risk = "HIGH"
        strength = "WEAK"
        color = "#fff3cd"
    else:
        signal = "WAIT FOR BREAKOUT"
        mood = "MIXED"
        risk = "MEDIUM"
        strength = "MEDIUM"
        color = "#fff3cd"

    gainers = sorted(rows, key=lambda x: x["pct"], reverse=True)[:5]
    losers = sorted(rows, key=lambda x: x["pct"])[:5]

    return render_template_string(
        HTML,
        signal=signal,
        color=color,
        green=green,
        red=red,
        flat=flat,
        green_pct=green_pct,
        red_pct=red_pct,
        bull_score=bull_score,
        put_score=put_score,
        mood=mood,
        risk=risk,
        strength=strength,
        weight_score=round(weight_score, 2),
        gainers=make_table(gainers),
        losers=make_table(losers),
        time=datetime.now().strftime("%d-%m-%Y %H:%M:%S")
  )
