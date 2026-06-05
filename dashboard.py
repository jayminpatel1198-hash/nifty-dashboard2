
from flask import Flask
import requests, os
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

weights = {"RELIANCE":9.47,"HDFCBANK":6.19,"BHARTIARTL":5.93,"SBIN":4.78,"ICICIBANK":4.75,"TCS":4.32,"INFY":2.64,"LT":2.90}

@app.route("/")
def home():
    if not TOKEN:
        return "UPSTOX_TOKEN missing"

    headers = {"Accept":"application/json","Authorization":"Bearer " + TOKEN}
    keys = ",".join(stocks.values())
    url = "https://api.upstox.com/v2/market-quote/quotes?instrument_key=" + keys

    try:
        data = requests.get(url, headers=headers, timeout=15).json()["data"]
    except Exception as e:
        return "API Error: " + str(e)

    green = red = flat = 0
    score = 0
    rows = []

    for s in data.values():
        symbol = s.get("symbol")
        price = s.get("last_price", 0)
        close = s.get("ohlc", {}).get("close", 0)
        change = s.get("net_change", 0)
        pct = round((change / close) * 100, 2) if close else 0

        if change > 0:
            green += 1
            score += weights.get(symbol, 0)
        elif change < 0:
            red += 1
            score -= weights.get(symbol, 0)
        else:
            flat += 1

        rows.append([symbol, price, pct])

    total = green + red + flat
    green_pct = round(green * 100 / total, 1)
    red_pct = round(red * 100 / total, 1)
    bull_score = max(0, min(100, round(50 + score, 1)))
    put_score = round(100 - bull_score, 1)

    if bull_score >= 70 and green_pct >= 60:
        signal = "STRONG CALL BIAS"
        color = "#d9fbe6"
    elif bull_score <= 30 and red_pct >= 60:
        signal = "STRONG PUT BIAS"
        color = "#ffe1e1"
    elif 45 <= green_pct <= 55:
        signal = "NO TRADE - SIDEWAYS"
        color = "#fff3cd"
    else:
        signal = "WAIT FOR BREAKOUT"
        color = "#fff3cd"

    gainers = sorted(rows, key=lambda x: x[2], reverse=True)[:5]
    losers = sorted(rows, key=lambda x: x[2])[:5]

    def table(data):
        out = ""
        for r in data:
            c = "green" if r[2] > 0 else "red"
            out += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td class='{c}'>{r[2]}%</td></tr>"
        return out

    return f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>Nifty Dashboard</title>
<style>
body {{font-family:Arial;background:#f4f6f8;padding:14px}}
.card {{background:white;padding:15px;margin:10px;border-radius:12px}}
.big {{font-size:25px;font-weight:bold}}
.green {{color:green;font-weight:bold}}
.red {{color:red;font-weight:bold}}
table {{width:100%;border-collapse:collapse}}
td,th {{padding:8px;border-bottom:1px solid #ddd}}
</style>
</head>
<body>
<h2>NIFTY OPTION DASHBOARD</h2>

<div class="card" style="background:{color}">
<h2>{signal}</h2>
</div>

<div class="card">Green: <span class="big green">{green} ({green_pct}%)</span></div>
<div class="card">Red: <span class="big red">{red} ({red_pct}%)</span></div>
<div class="card">Bull Score: <span class="big">{bull_score}/100</span></div>
<div class="card">Put Score: <span class="big">{put_score}/100</span></div>
<div class="card">Weight Score: <span class="big">{round(score,2)}</span></div>

<div class="card">
<h3>Top 5 Gainers</h3>
<table><tr><th>Stock</th><th>Price</th><th>%</th></tr>{table(gainers)}</table>
</div>

<div class="card">
<h3>Top 5 Losers</h3>
<table><tr><th>Stock</th><th>Price</th><th>%</th></tr>{table(losers)}</table>
</div>

<p>Updated: {datetime.now().strftime("%d-%m-%Y %H:%M:%S")}</p>
</body>
</html>
"""
    
