from flask import Flask, render_template_string
from markupsafe import Markup
import requests, os, xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote_plus

app = Flask(__name__)
TOKEN = os.environ.get("UPSTOX_TOKEN")

stocks = {
"HDFCBANK":"NSE_EQ|INE040A01034","RELIANCE":"NSE_EQ|INE002A01018","ICICIBANK":"NSE_EQ|INE090A01021","BHARTIARTL":"NSE_EQ|INE397D01024","LT":"NSE_EQ|INE018A01030","SBIN":"NSE_EQ|INE062A01020","INFY":"NSE_EQ|INE009A01021","AXISBANK":"NSE_EQ|INE238A01034","ITC":"NSE_EQ|INE154A01025","KOTAKBANK":"NSE_EQ|INE237A01036","M&M":"NSE_EQ|INE101A01026","TCS":"NSE_EQ|INE467B01029","BAJFINANCE":"NSE_EQ|INE296A01032","HINDUNILVR":"NSE_EQ|INE030A01027","SUNPHARMA":"NSE_EQ|INE044A01036","NTPC":"NSE_EQ|INE733E01010","TITAN":"NSE_EQ|INE280A01028","ETERNAL":"NSE_EQ|INE758T01015","TATASTEEL":"NSE_EQ|INE081A01020","MARUTI":"NSE_EQ|INE585B01010","BEL":"NSE_EQ|INE263A01024","HINDALCO":"NSE_EQ|INE038A01020","POWERGRID":"NSE_EQ|INE752E01010","ULTRACEMCO":"NSE_EQ|INE481G01011","SHRIRAMFIN":"NSE_EQ|INE721A01047","HCLTECH":"NSE_EQ|INE860A01027","ADANIPORTS":"NSE_EQ|INE742F01042","JSWSTEEL":"NSE_EQ|INE019A01038","ONGC":"NSE_EQ|INE213A01029","BAJAJ-AUTO":"NSE_EQ|INE917I01010","ASIANPAINT":"NSE_EQ|INE021A01026","COALINDIA":"NSE_EQ|INE522F01014","GRASIM":"NSE_EQ|INE047A01021","NESTLEIND":"NSE_EQ|INE239A01024","BAJAJFINSV":"NSE_EQ|INE918I01026","EICHERMOT":"NSE_EQ|INE066A01021","INDIGO":"NSE_EQ|INE646L01027","TECHM":"NSE_EQ|INE669C01036","TRENT":"NSE_EQ|INE849A01020","SBILIFE":"NSE_EQ|INE123W01016","DRREDDY":"NSE_EQ|INE089A01031","JIOFIN":"NSE_EQ|INE758E01017","APOLLOHOSP":"NSE_EQ|INE437A01024","TATACONSUM":"NSE_EQ|INE192A01025","CIPLA":"NSE_EQ|INE059A01026","MAXHEALTH":"NSE_EQ|INE027H01010","TMPV":"NSE_EQ|INE155A01022","ADANIENT":"NSE_EQ|INE423A01024","HDFCLIFE":"NSE_EQ|INE795G01014","WIPRO":"NSE_EQ|INE075A01022"
}

weights = {
"HDFCBANK":10.73,"RELIANCE":8.78,"ICICIBANK":8.21,"BHARTIARTL":5.26,"LT":4.28,"SBIN":4.03,"INFY":3.76,"AXISBANK":3.31,"ITC":2.76,"KOTAKBANK":2.56,"M&M":2.51,"TCS":2.30,"BAJFINANCE":2.28,"HINDUNILVR":1.81,"SUNPHARMA":1.74,"NTPC":1.72,"TITAN":1.64,"ETERNAL":1.62,"TATASTEEL":1.59,"MARUTI":1.59,"BEL":1.40,"HINDALCO":1.37,"POWERGRID":1.31,"ULTRACEMCO":1.25,"SHRIRAMFIN":1.19,"HCLTECH":1.15,"ADANIPORTS":1.11,"JSWSTEEL":1.08,"ONGC":1.06,"BAJAJ-AUTO":1.01,"ASIANPAINT":1.00,"COALINDIA":0.99,"GRASIM":0.97,"NESTLEIND":0.95,"BAJAJFINSV":0.92,"EICHERMOT":0.89,"INDIGO":0.88,"TECHM":0.85,"TRENT":0.84,"SBILIFE":0.74,"DRREDDY":0.73,"JIOFIN":0.73,"APOLLOHOSP":0.71,"TATACONSUM":0.68,"CIPLA":0.67,"MAXHEALTH":0.67,"TMPV":0.65,"ADANIENT":0.63,"HDFCLIFE":0.57,"WIPRO":0.52
}

HTML = """
<html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Nifty 50 Full Dashboard</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0;padding:8px}
.card{background:white;padding:12px;margin:7px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.signal{padding:17px;border-radius:16px;text-align:center;font-size:24px;font-weight:bold;margin:7px}
.big{font-size:24px;font-weight:bold}.green{color:green;font-weight:bold}.red{color:red;font-weight:bold}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.box{background:#f8f9fa;border-radius:12px;padding:9px;text-align:center}
.label{font-size:12px;color:#555}.val{font-size:19px;font-weight:bold}
.meters{display:flex;gap:7px}.meterbox{flex:1;text-align:center}
.gauge{width:150px;height:95px;margin:4px auto;position:relative;overflow:hidden}
.gauge:before{content:"";position:absolute;left:10px;top:10px;width:130px;height:130px;border-radius:50%;background:conic-gradient(from 270deg,#d93025 0deg 80deg,#fbbc04 80deg 100deg,#0a9f45 100deg 180deg,transparent 180deg 360deg)}
.gauge:after{content:"";position:absolute;left:33px;top:33px;width:84px;height:84px;background:white;border-radius:50%}
.needle{position:absolute;left:73px;top:72px;width:4px;height:55px;background:#111;transform-origin:2px 2px;z-index:3}
.center{position:absolute;left:66px;top:65px;width:18px;height:18px;background:#111;border-radius:50%;z-index:4}
.score{position:absolute;left:0;right:0;top:54px;text-align:center;font-size:22px;font-weight:bold;z-index:5}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:6px;border-bottom:1px solid #ddd;text-align:left}
.news{font-size:13px;margin:5px 0}.small{text-align:center;color:#555;font-size:12px}
</style></head><body>

<div class="card">NIFTY LIVE: <span class="big">{{ nifty_price }}</span></div>
<div class="signal" style="background:{{ color }}">{{ decision }}</div>

<div class="meters">
<div class="card meterbox"><h3>Weight</h3><div class="gauge"><div class="needle" style="transform:rotate({{ weight_angle }}deg)"></div><div class="center"></div><div class="score">{{ weight_score }}</div></div></div>
<div class="card meterbox"><h3>Price</h3><div class="gauge"><div class="needle" style="transform:rotate({{ price_angle }}deg)"></div><div class="center"></div><div class="score">{{ price_score }}</div></div></div>
</div>

<div class="card">
<div class="grid">
<div class="box"><div class="label">Loaded Stocks</div><div class="val">{{ loaded }}/50</div></div>
<div class="box"><div class="label">Market Power</div><div class="val">{{ market_power }}/100</div></div>
<div class="box"><div class="label">Plus Stocks</div><div class="val green">{{ green }}</div></div>
<div class="box"><div class="label">Minus Stocks</div><div class="val red">{{ red }}</div></div>
<div class="box"><div class="label">Total ₹ Plus</div><div class="val green">+{{ total_plus }}</div></div>
<div class="box"><div class="label">Total ₹ Minus</div><div class="val red">{{ total_minus }}</div></div>
<div class="box"><div class="label">Net ₹ Change</div><div class="val">{{ net_price }}</div></div>
<div class="box"><div class="label">News Effect</div><div class="val">{{ news_effect }}</div></div>
<div class="box"><div class="label">Weight Plus</div><div class="val green">+{{ weight_plus }}</div></div>
<div class="box"><div class="label">Weight Minus</div><div class="val red">{{ weight_minus }}</div></div>
<div class="box"><div class="label">Net Weight Effect</div><div class="val">{{ net_effect }}</div></div>
<div class="box"><div class="label">Call / Put</div><div class="val"><span class="green">{{ call_p }}%</span> / <span class="red">{{ put_p }}%</span></div></div>
</div>
</div>

<div class="card">
<h3>One Line News Impact</h3>
{{ news_rows }}
</div>

<div class="card">
<h3>Top Nifty Drivers</h3>
<table><tr><th>Stock</th><th>₹</th><th>%</th><th>Wt</th><th>Effect</th></tr>{{ drivers }}</table>
</div>

<div class="card">
<h3>All 50 Stocks</h3>
<table><tr><th>Stock</th><th>Price</th><th>₹</th><th>%</th><th>Wt</th><th>Effect</th></tr>{{ rows }}</table>
</div>

<p class="small">Auto refresh 30 sec | Updated: {{ time }}</p>
</body></html>
"""

def fetch_news():
    qs = ["Nifty 50 latest market news India", "RBI crude oil rupee US market Nifty", "HDFC Bank Reliance ICICI Nifty news"]
    news = []
    for q in qs:
        try:
            url = "https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=en-IN&gl=IN&ceid=IN:en"
            r = requests.get(url, timeout=5, headers={"User-Agent":"Mozilla/5.0"})
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:2]:
                title = item.findtext("title","")
                if title and title not in [n["title"] for n in news]:
                    news.append({"title":title})
        except:
            pass
    return news[:6]

def calc_news(news):
    bull = ["rises","rise","gain","gains","higher","rally","surge","buying","positive","rate cut","oil falls","rupee gains","strong"]
    bear = ["falls","fall","lower","slump","selling","selloff","weak","rate hike","oil rises","war","inflation","tension"]
    score = 0
    rows = ""
    for n in news:
        t = n["title"].lower()
        val = 0
        for w in bull:
            if w in t: val += 5
        for w in bear:
            if w in t: val -= 5
        if val > 0:
            rows += f"<div class='news green'>🟢 +{val} {n['title']}</div>"
        elif val < 0:
            rows += f"<div class='news red'>🔴 {val} {n['title']}</div>"
        else:
            rows += f"<div class='news'>⚪ 0 {n['title']}</div>"
        score += val
    return max(-30, min(30, score)), Markup(rows or "<div>No news loaded</div>")

def make_rows(items, short=False):
    out = ""
    for r in items:
        c = "green" if r["effect"] > 0 else "red"
        rc = "green" if r["rupee"] > 0 else "red"
        if short:
            out += f"<tr><td>{r['symbol']}</td><td class='{rc}'>{r['rupee']}</td><td class='{c}'>{r['pct']}%</td><td>{r['weight']}%</td><td class='{c}'>{r['effect']}</td></tr>"
        else:
            out += f"<tr><td>{r['symbol']}</td><td>{r['price']}</td><td class='{rc}'>{r['rupee']}</td><td class='{c}'>{r['pct']}%</td><td>{r['weight']}%</td><td class='{c}'>{r['effect']}</td></tr>"
    return Markup(out)

@app.route("/")
def home():
    if not TOKEN:
        return "UPSTOX_TOKEN missing"

    headers = {"Accept":"application/json","Authorization":"Bearer " + TOKEN}

    try:
        n = requests.get("https://api.upstox.com/v2/market-quote/ltp", headers=headers, params={"instrument_key":"NSE_INDEX|Nifty 50"}, timeout=10).json()
        nifty_price = n["data"]["NSE_INDEX:Nifty 50"]["last_price"]
    except:
        nifty_price = "Error"

    try:
        q = requests.get("https://api.upstox.com/v2/market-quote/quotes", headers=headers, params={"instrument_key":",".join(stocks.values())}, timeout=15).json()["data"]
    except Exception as e:
        return "Upstox API Error: " + str(e)

    green = red = 0
    weight_plus = weight_minus = 0
    total_plus = total_minus = 0
    rows = []
    loaded_symbols = set()

    for s in q.values():
        symbol = s.get("symbol","")
        if symbol not in weights:
            for k in weights.keys():
                if k in str(s):
                    symbol = k
                    break

        price = round(s.get("last_price",0),2)
        close = s.get("ohlc",{}).get("close",0)
        rupee = round(s.get("net_change",0),2)
        pct = round((rupee / close) * 100,2) if close else 0
        wt = weights.get(symbol,0)
        effect = round(wt * pct,2)

        if symbol:
            loaded_symbols.add(symbol)

        if rupee > 0:
            green += 1
            weight_plus += effect
            total_plus += rupee
        elif rupee < 0:
            red += 1
            weight_minus += effect
            total_minus += rupee

        rows.append({"symbol":symbol,"price":price,"rupee":rupee,"pct":pct,"weight":wt,"effect":effect})

    weight_plus = round(weight_plus,2)
    weight_minus = round(weight_minus,2)
    net_effect = round(weight_plus + weight_minus,2)
    total_plus = round(total_plus,2)
    total_minus = round(total_minus,2)
    net_price = round(total_plus + total_minus,2)

    weight_abs = weight_plus + abs(weight_minus)
    weight_score = round((weight_plus / weight_abs) * 100,1) if weight_abs > 0 else 50

    price_abs = total_plus + abs(total_minus)
    price_score = round((total_plus / price_abs) * 100,1) if price_abs > 0 else 50

    news_effect, news_rows = calc_news(fetch_news())
    news_score = 50 + news_effect

    market_power = round((weight_score * 0.60) + (price_score * 0.25) + (news_score * 0.15),1)
    call_p = market_power
    put_p = round(100 - market_power,1)

    weight_angle = round(-90 + weight_score * 1.8,1)
    price_angle = round(-90 + price_score * 1.8,1)

    if market_power >= 70:
        decision, color = "✅ CALL BUY - STRONG BULLISH", "#d9fbe6"
    elif market_power >= 60:
        decision, color = "🟢 CALL SIDE WATCH", "#fff3cd"
    elif market_power <= 30:
        decision, color = "✅ PUT BUY - STRONG BEARISH", "#ffe1e1"
    elif market_power <= 40:
        decision, color = "🔴 PUT SIDE WATCH", "#fff3cd"
    else:
        decision, color = "⚠ NO TRADE / SIDEWAYS", "#fff3cd"

    drivers_sorted = sorted(rows, key=lambda x:abs(x["effect"]), reverse=True)[:10]
    all_sorted = sorted(rows, key=lambda x:x["effect"], reverse=True)

    return render_template_string(
        HTML,
        nifty_price=nifty_price,
        decision=decision,
        color=color,
        loaded=len(rows),
        market_power=market_power,
        green=green,
        red=red,
        total_plus=total_plus,
        total_minus=total_minus,
        net_price=net_price,
        weight_plus=weight_plus,
        weight_minus=weight_minus,
        net_effect=net_effect,
        weight_score=weight_score,
        price_score=price_score,
        weight_angle=weight_angle,
        price_angle=price_angle,
        news_effect=news_effect,
        news_rows=news_rows,
        call_p=call_p,
        put_p=put_p,
        drivers=make_rows(drivers_sorted, True),
        rows=make_rows(all_sorted),
        time=datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    )
