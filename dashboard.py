from flask import Flask, render_template_string
from markupsafe import Markup
import requests, os
from datetime import datetime

app = Flask(__name__)
TOKEN = os.environ.get("UPSTOX_TOKEN")

stocks = {
"HDFCBANK":"NSE_EQ|INE040A01034","RELIANCE":"NSE_EQ|INE002A01018","ICICIBANK":"NSE_EQ|INE090A01021","BHARTIARTL":"NSE_EQ|INE397D01024","LT":"NSE_EQ|INE018A01030","SBIN":"NSE_EQ|INE062A01020","INFY":"NSE_EQ|INE009A01021","AXISBANK":"NSE_EQ|INE238A01034","ITC":"NSE_EQ|INE154A01025","KOTAKBANK":"NSE_EQ|INE237A01036","M&M":"NSE_EQ|INE101A01026","TCS":"NSE_EQ|INE467B01029","BAJFINANCE":"NSE_EQ|INE296A01032","HINDUNILVR":"NSE_EQ|INE030A01027","SUNPHARMA":"NSE_EQ|INE044A01036","NTPC":"NSE_EQ|INE733E01010","TITAN":"NSE_EQ|INE280A01028","ETERNAL":"NSE_EQ|INE758T01015","TATASTEEL":"NSE_EQ|INE081A01020","MARUTI":"NSE_EQ|INE585B01010","BEL":"NSE_EQ|INE263A01024","HINDALCO":"NSE_EQ|INE038A01020","POWERGRID":"NSE_EQ|INE752E01010","ULTRACEMCO":"NSE_EQ|INE481G01011","SHRIRAMFIN":"NSE_EQ|INE721A01047","HCLTECH":"NSE_EQ|INE860A01027","ADANIPORTS":"NSE_EQ|INE742F01042","JSWSTEEL":"NSE_EQ|INE019A01038","ONGC":"NSE_EQ|INE213A01029","BAJAJ-AUTO":"NSE_EQ|INE917I01010","ASIANPAINT":"NSE_EQ|INE021A01026","COALINDIA":"NSE_EQ|INE522F01014","GRASIM":"NSE_EQ|INE047A01021","NESTLEIND":"NSE_EQ|INE239A01024","BAJAJFINSV":"NSE_EQ|INE918I01026","EICHERMOT":"NSE_EQ|INE066A01021","INDIGO":"NSE_EQ|INE646L01027","TECHM":"NSE_EQ|INE669C01036","TRENT":"NSE_EQ|INE849A01020","SBILIFE":"NSE_EQ|INE123W01016","DRREDDY":"NSE_EQ|INE089A01031","JIOFIN":"NSE_EQ|INE758E01017","APOLLOHOSP":"NSE_EQ|INE437A01024","TATACONSUM":"NSE_EQ|INE192A01025","CIPLA":"NSE_EQ|INE059A01026","MAXHEALTH":"NSE_EQ|INE027H01010","TMPV":"NSE_EQ|INE155A01022","ADANIENT":"NSE_EQ|INE423A01024","HDFCLIFE":"NSE_EQ|INE795G01014","WIPRO":"NSE_EQ|INE075A01022"
}

weights = {
"HDFCBANK":10.73,"RELIANCE":8.78,"ICICIBANK":8.21,"BHARTIARTL":5.26,"LT":4.28,"SBIN":4.03,"INFY":3.76,"AXISBANK":3.31,"ITC":2.76,"KOTAKBANK":2.56,"M&M":2.51,"TCS":2.30,"BAJFINANCE":2.28,"HINDUNILVR":1.81,"SUNPHARMA":1.74,"NTPC":1.72,"TITAN":1.64,"ETERNAL":1.62,"TATASTEEL":1.59,"MARUTI":1.59,"BEL":1.40,"HINDALCO":1.37,"POWERGRID":1.31,"ULTRACEMCO":1.25,"SHRIRAMFIN":1.19,"HCLTECH":1.15,"ADANIPORTS":1.11,"JSWSTEEL":1.08,"ONGC":1.06,"BAJAJ-AUTO":1.01,"ASIANPAINT":1.00,"COALINDIA":0.99,"GRASIM":0.97,"NESTLEIND":0.95,"BAJAJFINSV":0.92,"EICHERMOT":0.89,"INDIGO":0.88,"TECHM":0.85,"TRENT":0.84,"SBILIFE":0.74,"DRREDDY":0.73,"JIOFIN":0.73,"APOLLOHOSP":0.71,"TATACONSUM":0.68,"CIPLA":0.67,"MAXHEALTH":0.67,"TMPV":0.65,"ADANIENT":0.63,"HDFCLIFE":0.57,"WIPRO":0.52
}

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>Nifty Impact Dashboard V9</title>
<style>
body{font-family:Arial;background:#f4f6f8;padding:12px;margin:0}
h2{text-align:center}.card{background:white;padding:14px;margin:8px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.signal{padding:18px;border-radius:16px;text-align:center;font-size:23px;font-weight:bold;margin:8px}
.big{font-size:23px;font-weight:bold}.green{color:green;font-weight:bold}.red{color:red;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:7px;border-bottom:1px solid #ddd;text-align:left}
.small{text-align:center;color:#555}
</style>
</head>
<body>
<h2>NIFTY IMPACT DASHBOARD V9</h2>

<div class="card">Nifty 50 Live: <span class="big">{{ nifty_price }}</span></div>
<div class="signal" style="background:{{ color }}">{{ final_decision }}</div>

<div class="card">Direction: <span class="big">{{ direction }}</span></div>
<div class="card">Reason: <span class="big">{{ reason }}</span></div>

<div class="card">Green Stocks: <span class="big green">{{ green }} ({{ green_pct }}%)</span></div>
<div class="card">Red Stocks: <span class="big red">{{ red }} ({{ red_pct }}%)</span></div>

<div class="card">Total ₹ Plus: <span class="big green">+{{ total_rupee_plus }}</span></div>
<div class="card">Total ₹ Minus: <span class="big red">{{ total_rupee_minus }}</span></div>
<div class="card">Net ₹ Move: <span class="big">{{ net_rupee }}</span></div>

<div class="card">Positive Impact: <span class="big green">+{{ positive_impact }}</span></div>
<div class="card">Negative Impact: <span class="big red">{{ negative_impact }}</span></div>
<div class="card">Net Impact: <span class="big">{{ net_impact }}</span></div>

<div class="card">Call Pressure: <span class="big green">{{ call_pressure }}%</span></div>
<div class="card">Put Pressure: <span class="big red">{{ put_pressure }}%</span></div>
<div class="card">Entry Advice: <span class="big">{{ entry_advice }}</span></div>

<div class="card">
<h3>Top 10 Pullers</h3>
<table><tr><th>Stock</th><th>Price</th><th>₹ Chg</th><th>%</th><th>Wt</th><th>Impact</th></tr>{{ pullers }}</table>
</div>

<div class="card">
<h3>Top 10 Draggers</h3>
<table><tr><th>Stock</th><th>Price</th><th>₹ Chg</th><th>%</th><th>Wt</th><th>Impact</th></tr>{{ draggers }}</table>
</div>

<div class="card">
<h3>All 50 Stocks Live Impact</h3>
<table><tr><th>Stock</th><th>Price</th><th>₹ Chg</th><th>%</th><th>Wt</th><th>Impact</th></tr>{{ all_rows }}</table>
</div>

<p class="small">Auto refresh 5 sec | Updated: {{ time }}</p>
</body>
</html>
"""

def make_rows(items):
    out = ""
    for r in items:
        cls = "green" if r["impact"] > 0 else "red"
        rupee_cls = "green" if r["rupee"] > 0 else "red"
        out += f"<tr><td>{r['symbol']}</td><td>{r['price']}</td><td class='{rupee_cls}'>{r['rupee']}</td><td class='{cls}'>{r['pct']}%</td><td>{r['weight']}%</td><td class='{cls}'>{r['impact']}</td></tr>"
    return Markup(out)

@app.route("/")
def home():
    if not TOKEN:
        return "UPSTOX_TOKEN missing in Render Environment"

    headers = {"Accept":"application/json","Authorization":"Bearer " + TOKEN}

    try:
        nres = requests.get("https://api.upstox.com/v2/market-quote/ltp",
            headers=headers, params={"instrument_key":"NSE_INDEX|Nifty 50"}, timeout=10)
        nifty_price = nres.json()["data"]["NSE_INDEX:Nifty 50"]["last_price"]
    except:
        nifty_price = "Error"

    try:
        res = requests.get("https://api.upstox.com/v2/market-quote/quotes",
            headers=headers, params={"instrument_key":",".join(stocks.values())}, timeout=15)
        data = res.json()["data"]
    except Exception as e:
        return "Upstox API Error: " + str(e)

    green = red = flat = 0
    total_rupee_plus = 0
    total_rupee_minus = 0
    positive_impact = 0
    negative_impact = 0
    rows = []

    for s in data.values():
        symbol = s.get("symbol","")
        price = round(s.get("last_price",0),2)
        close = s.get("ohlc",{}).get("close",0)
        rupee = round(s.get("net_change",0),2)
        pct = round((rupee / close) * 100, 2) if close else 0
        wt = weights.get(symbol,0)
        impact = round(wt * pct, 2)

        if rupee > 0:
            green += 1
            total_rupee_plus += rupee
            positive_impact += impact
        elif rupee < 0:
            red += 1
            total_rupee_minus += rupee
            negative_impact += impact
        else:
            flat += 1

        rows.append({
            "symbol":symbol,"price":price,"rupee":rupee,
            "pct":pct,"weight":wt,"impact":impact
        })

    total = green + red + flat
    green_pct = round(green * 100 / total,1) if total else 0
    red_pct = round(red * 100 / total,1) if total else 0

    total_rupee_plus = round(total_rupee_plus,2)
    total_rupee_minus = round(total_rupee_minus,2)
    net_rupee = round(total_rupee_plus + total_rupee_minus,2)

    positive_impact = round(positive_impact,2)
    negative_impact = round(negative_impact,2)
    net_impact = round(positive_impact + negative_impact,2)

    call_pressure = max(0, min(100, round(50 + net_impact,1)))
    put_pressure = max(0, min(100, round(50 - net_impact,1)))

    if net_impact >= 8:
        final_decision = "CALL BUY FAVOURABLE"
        direction = "CALL SIDE STRONG"
        entry_advice = "Call only after breakout confirmation"
        color = "#d9fbe6"
        reason = "Weighted positive impact strong છે."
    elif net_impact <= -8:
        final_decision = "PUT BUY FAVOURABLE"
        direction = "PUT SIDE STRONG"
        entry_advice = "Put only after breakdown confirmation"
        color = "#ffe1e1"
        reason = "Weighted negative impact strong છે."
    elif net_impact > 2:
        final_decision = "CALL SIDE WATCH"
        direction = "MILD BULLISH"
        entry_advice = "Wait for breakout"
        color = "#fff3cd"
        reason = "Positive impact છે, પણ strong નથી."
    elif net_impact < -2:
        final_decision = "PUT SIDE WATCH"
        direction = "MILD BEARISH"
        entry_advice = "Wait for breakdown"
        color = "#fff3cd"
        reason = "Negative impact છે, પણ strong નથી."
    else:
        final_decision = "NO TRADE"
        direction = "CHOPPY / SIDEWAYS"
        entry_advice = "Avoid option buying"
        color = "#fff3cd"
        reason = "Net impact weak છે."

    pullers = sorted([r for r in rows if r["impact"] > 0], key=lambda x: x["impact"], reverse=True)[:10]
    draggers = sorted([r for r in rows if r["impact"] < 0], key=lambda x: x["impact"])[:10]
    all_sorted = sorted(rows, key=lambda x: x["impact"], reverse=True)

    return render_template_string(
        HTML,
        nifty_price=nifty_price,
        final_decision=final_decision,
        color=color,
        direction=direction,
        reason=reason,
        green=green,
        red=red,
        green_pct=green_pct,
        red_pct=red_pct,
        total_rupee_plus=total_rupee_plus,
        total_rupee_minus=total_rupee_minus,
        net_rupee=net_rupee,
        positive_impact=positive_impact,
        negative_impact=negative_impact,
        net_impact=net_impact,
        call_pressure=call_pressure,
        put_pressure=put_pressure,
        entry_advice=entry_advice,
        pullers=make_rows(pullers),
        draggers=make_rows(draggers),
        all_rows=make_rows(all_sorted),
        time=datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        )
