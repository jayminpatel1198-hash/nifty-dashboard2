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
<title>Nifty Weight Dashboard V7</title>
<style>
body{font-family:Arial;background:#f4f6f8;padding:14px;margin:0}
h2{text-align:center}
.card{background:white;padding:15px;margin:10px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.signal{padding:20px;border-radius:16px;text-align:center;font-size:24px;font-weight:bold;margin:10px}
.big{font-size:24px;font-weight:bold}
.green{color:green;font-weight:bold}
.red{color:red;font-weight:bold}
table{width:100%;border-collapse:collapse}
td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}
.small{text-align:center;color:#555}
</style>
</head>
<body>
<h2>NIFTY WEIGHTAGE DASHBOARD V7</h2>

<div class="card">Nifty 50 Live: <span class="big">{{ nifty_price }}</span></div>
<div class="signal" style="background:{{ color }}">{{ final_decision }}</div>

<div class="card">Market Pull: <span class="big">{{ pull_direction }}</span></div>
<div class="card">Reason: <span class="big">{{ reason }}</span></div>

<div class="card">Stock Count Green: <span class="big green">{{ green }} ({{ green_pct }}%)</span></div>
<div class="card">Stock Count Red: <span class="big red">{{ red }} ({{ red_pct }}%)</span></div>
<div class="card">Green Weight: <span class="big green">{{ green_weight }}%</span></div>
<div class="card">Red Weight: <span class="big red">{{ red_weight }}%</span></div>
<div class="card">Net Weight: <span class="big">{{ net_weight }}</span></div>

<div class="card">Call Pressure: <span class="big green">{{ call_pressure }}%</span></div>
<div class="card">Put Pressure: <span class="big red">{{ put_pressure }}%</span></div>
<div class="card">Option Risk: <span class="big">{{ option_risk }}</span></div>
<div class="card">Entry Advice: <span class="big">{{ entry_advice }}</span></div>

<div class="card">
<h3>Weightage Bucket Summary</h3>
<table>
<tr><th>Bucket</th><th>Green</th><th>Red</th><th>Green Wt</th><th>Red Wt</th><th>Net</th></tr>
{{ bucket_rows }}
</table>
</div>

<div class="card">
<h3>Top Pullers / Draggers</h3>
<table><tr><th>Stock</th><th>Wt</th><th>% Chg</th><th>Impact</th></tr>{{ contributor_rows }}</table>
</div>

<div class="card"><h3>Top 5 Gainers</h3><table><tr><th>Stock</th><th>Price</th><th>%</th></tr>{{ gainers }}</table></div>
<div class="card"><h3>Top 5 Losers</h3><table><tr><th>Stock</th><th>Price</th><th>%</th></tr>{{ losers }}</table></div>

<p class="small">Auto refresh 5 sec | Updated: {{ time }}</p>
</body>
</html>
"""

def bucket_name(w):
    if w >= 5:
        return "5%+ Heavyweight"
    elif w >= 2:
        return "2% to 5%"
    elif w >= 1:
        return "1% to 2%"
    return "Below 1%"

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

    headers = {"Accept":"application/json","Authorization":"Bearer " + TOKEN}

    try:
        nres = requests.get("https://api.upstox.com/v2/market-quote/ltp", headers=headers, params={"instrument_key":"NSE_INDEX|Nifty 50"}, timeout=10)
        nifty_price = nres.json()["data"]["NSE_INDEX:Nifty 50"]["last_price"]
    except:
        nifty_price = "Error"

    try:
        res = requests.get("https://api.upstox.com/v2/market-quote/quotes", headers=headers, params={"instrument_key":",".join(stocks.values())}, timeout=15)
        data = res.json()["data"]
    except Exception as e:
        return "Upstox API Error: " + str(e)

    green = red = flat = 0
    green_weight = red_weight = 0
    rows, contributors = [], []

    buckets = {
        "5%+ Heavyweight":{"g":0,"r":0,"gw":0,"rw":0},
        "2% to 5%":{"g":0,"r":0,"gw":0,"rw":0},
        "1% to 2%":{"g":0,"r":0,"gw":0,"rw":0},
        "Below 1%":{"g":0,"r":0,"gw":0,"rw":0}
    }

    for s in data.values():
        symbol = s.get("symbol","")
        price = s.get("last_price",0)
        close = s.get("ohlc",{}).get("close",0)
        change = s.get("net_change",0)
        pct = round((change / close) * 100, 2) if close else 0
        wt = weights.get(symbol,0)
        b = bucket_name(wt)

        if change > 0:
            green += 1
            green_weight += wt
            buckets[b]["g"] += 1
            buckets[b]["gw"] += wt
        elif change < 0:
            red += 1
            red_weight += wt
            buckets[b]["r"] += 1
            buckets[b]["rw"] += wt
        else:
            flat += 1

        impact = round(wt * pct, 2)
        contributors.append({"symbol":symbol,"weight":wt,"pct":pct,"impact":impact})
        rows.append({"symbol":symbol,"price":price,"pct":pct})

    total = green + red + flat
    green_pct = round(green * 100 / total, 1) if total else 0
    red_pct = round(red * 100 / total, 1) if total else 0

    green_weight = round(green_weight,2)
    red_weight = round(red_weight,2)
    net_weight = round(green_weight - red_weight,2)

    call_pressure = round((green_pct * 0.35) + ((50 + net_weight) * 0.65),1)
    put_pressure = round((red_pct * 0.35) + ((50 - net_weight) * 0.65),1)
    call_pressure = max(0, min(100, call_pressure))
    put_pressure = max(0, min(100, put_pressure))

    if green_weight > red_weight and red > green:
        pull_direction = "Heavyweights pulling market UP"
        reason = "Stocks red વધારે છે, પણ green weight વધારે છે."
    elif red_weight > green_weight and green > red:
        pull_direction = "Heavyweights pulling market DOWN"
        reason = "Stocks green વધારે છે, પણ red weight વધારે છે."
    elif green_weight > red_weight:
        pull_direction = "Weight bullish"
        reason = "Green side weight વધારે છે."
    elif red_weight > green_weight:
        pull_direction = "Weight bearish"
        reason = "Red side weight વધારે છે."
    else:
        pull_direction = "Balanced"
        reason = "Green અને red weight નજીક છે."

    if call_pressure >= 75 and green_weight > red_weight:
        final_decision, entry_advice, option_risk, color = "CALL BUY FAVOURABLE", "Only after breakout confirmation", "LOW", "#d9fbe6"
    elif put_pressure >= 75 and red_weight > green_weight:
        final_decision, entry_advice, option_risk, color = "PUT BUY FAVOURABLE", "Only after breakdown confirmation", "LOW", "#ffe1e1"
    elif green_weight > red_weight:
        final_decision, entry_advice, option_risk, color = "CALL SIDE WATCH", "Wait for breakout", "MEDIUM", "#fff3cd"
    elif red_weight > green_weight:
        final_decision, entry_advice, option_risk, color = "PUT SIDE WATCH", "Wait for breakdown", "MEDIUM", "#fff3cd"
    else:
        final_decision, entry_advice, option_risk, color = "NO TRADE", "Avoid option buying", "HIGH", "#fff3cd"

    bucket_html = ""
    for name, b in buckets.items():
        net = round(b["gw"] - b["rw"],2)
        bucket_html += f"<tr><td>{name}</td><td class='green'>{b['g']}</td><td class='red'>{b['r']}</td><td class='green'>{round(b['gw'],2)}%</td><td class='red'>{round(b['rw'],2)}%</td><td>{net}</td></tr>"

    top_contributors = sorted(contributors, key=lambda x: abs(x["impact"]), reverse=True)[:10]
    contributor_html = ""
    for c in top_contributors:
        cls = "green" if c["impact"] > 0 else "red"
        contributor_html += f"<tr><td>{c['symbol']}</td><td>{c['weight']}%</td><td>{c['pct']}%</td><td class='{cls}'>{c['impact']}</td></tr>"

    gainers = sorted(rows, key=lambda x: x["pct"], reverse=True)[:5]
    losers = sorted(rows, key=lambda x: x["pct"])[:5]

    return render_template_string(HTML, nifty_price=nifty_price, final_decision=final_decision, color=color, pull_direction=pull_direction, reason=reason, green=green, red=red, green_pct=green_pct, red_pct=red_pct, green_weight=green_weight, red_weight=red_weight, net_weight=net_weight, call_pressure=call_pressure, put_pressure=put_pressure, option_risk=option_risk, entry_advice=entry_advice, bucket_rows=Markup(bucket_html), contributor_rows=Markup(contributor_html), gainers=make_table(gainers), losers=make_table(losers), time=datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
