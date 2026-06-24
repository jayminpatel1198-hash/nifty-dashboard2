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
<meta http-equiv="refresh" content="60">
<title>Nifty News Impact Dashboard</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0;padding:8px}
h2{text-align:center;margin:8px}.card{background:white;padding:12px;margin:7px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.signal{padding:16px;border-radius:16px;text-align:center;font-size:23px;font-weight:bold;margin:7px}
.big{font-size:23px;font-weight:bold}.green{color:green;font-weight:bold}.red{color:red;font-weight:bold}.orange{color:#b36b00;font-weight:bold}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.box{background:#f8f9fa;border-radius:12px;padding:10px;text-align:center}
.label{font-size:12px;color:#555}.val{font-size:19px;font-weight:bold}
.meters{display:flex;gap:7px;flex-wrap:nowrap}.meterbox{flex:1;text-align:center;min-width:0}
.gauge{width:115px;height:78px;margin:3px auto;position:relative;overflow:hidden}
.gauge:before{content:"";position:absolute;left:8px;top:8px;width:100px;height:100px;border-radius:50%;background:conic-gradient(from 270deg,#d93025 0deg 80deg,#fbbc04 80deg 100deg,#0a9f45 100deg 180deg,transparent 180deg 360deg)}
.gauge:after{content:"";position:absolute;left:28px;top:28px;width:60px;height:60px;background:white;border-radius:50%}
.needle{position:absolute;left:56px;top:58px;width:4px;height:42px;background:#111;transform-origin:2px 2px;z-index:3}
.center{position:absolute;left:50px;top:52px;width:16px;height:16px;background:#111;border-radius:50%;z-index:4}
.score{position:absolute;left:0;right:0;top:43px;text-align:center;font-size:20px;font-weight:bold;z-index:5}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:6px;border-bottom:1px solid #ddd;text-align:left}
.newsitem{font-size:13px;margin:6px 0}.small{text-align:center;color:#555;font-size:12px}
</style></head>
<body>
<h2>NIFTY NEWS + OPTION DASHBOARD</h2>

<div class="card">Nifty 50 Live: <span class="big">{{ nifty_price }}</span></div>

<div class="meters">
<div class="card meterbox"><h3>Weight</h3><div class="gauge"><div class="needle" style="transform:rotate({{ weight_angle }}deg)"></div><div class="center"></div><div class="score">{{ weight_meter }}</div></div></div>
<div class="card meterbox"><h3>Price</h3><div class="gauge"><div class="needle" style="transform:rotate({{ price_angle }}deg)"></div><div class="center"></div><div class="score">{{ price_meter }}</div></div></div>
<div class="card meterbox"><h3>News</h3><div class="gauge"><div class="needle" style="transform:rotate({{ news_angle }}deg)"></div><div class="center"></div><div class="score">{{ news_meter }}</div></div></div>
</div>

<div class="signal" style="background:{{ color }}">{{ final_decision }}</div>

<div class="card">
<div class="grid">
<div class="box"><div class="label">Net Price</div><div class="val">{{ net_price_change }}</div></div>
<div class="box"><div class="label">Net Weight Effect</div><div class="val">{{ net_effect }}</div></div>
<div class="box"><div class="label">News Score</div><div class="val">{{ news_meter }}</div></div>
<div class="box"><div class="label">Final Score</div><div class="val">{{ final_score }}</div></div>
<div class="box"><div class="label">Green / Red</div><div class="val"><span class="green">{{ green }}</span> / <span class="red">{{ red }}</span></div></div>
<div class="box"><div class="label">Buy / Sell</div><div class="val"><span class="green">{{ buy_pressure }}%</span> / <span class="red">{{ sell_pressure }}%</span></div></div>
</div>
</div>

<div class="card">
<h3>News Impact</h3>
<div>{{ news_rows }}</div>
</div>

<div class="card">
<h3>All 50 Stocks</h3>
<table><tr><th>Stock</th><th>Price</th><th>₹</th><th>%</th><th>Wt</th><th>Effect</th></tr>{{ rows }}</table>
</div>

<p class="small">Auto refresh 60 sec | Updated: {{ time }}</p>
</body></html>
"""

def fetch_news():
    queries = [
        "Nifty 50 market news India",
        "RBI policy stock market India",
        "FII DII data Nifty",
        "crude oil rupee Nifty impact",
        "HDFC Bank Reliance ICICI Bank Nifty news"
    ]
    titles = []
    for q in queries:
        try:
            url = "https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=en-IN&gl=IN&ceid=IN:en"
            r = requests.get(url, timeout=6, headers={"User-Agent":"Mozilla/5.0"})
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:2]:
                title = item.findtext("title", "")
                link = item.findtext("link", "#")
                if title and title not in [x["title"] for x in titles]:
                    titles.append({"title": title, "link": link})
        except:
            pass
    return titles[:8]

def news_score(news):
    bullish = ["rises","rise","gain","gains","higher","surge","rally","positive","buying","cuts","rate cut","oil falls","crude falls","rupee gains","strong"]
    bearish = ["falls","fall","lower","slump","selloff","selling","weak","inflation","rate hike","oil rises","crude rises","war","tension","fii selling"]
    score = 50
    for n in news:
        t = n["title"].lower()
        for w in bullish:
            if w in t: score += 4
        for w in bearish:
            if w in t: score -= 4
    return max(0, min(100, score))

def make_news_rows(news):
    if not news:
        return Markup("<div class='newsitem'>News not loaded.</div>")
    out = ""
    for n in news:
        out += f"<div class='newsitem'>• <a href='{n['link']}' target='_blank'>{n['title']}</a></div>"
    return Markup(out)

def make_table(rows):
    html = ""
    for r in rows:
        cls = "green" if r["effect"] > 0 else "red"
        rc = "green" if r["rupee"] > 0 else "red"
        html += f"<tr><td>{r['symbol']}</td><td>{r['price']}</td><td class='{rc}'>{r['rupee']}</td><td class='{cls}'>{r['pct']}%</td><td>{r['weight']}%</td><td class='{cls}'>{r['effect']}</td></tr>"
    return Markup(html)

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

    green = red = 0
    total_price_up = total_price_down = 0
    positive_effect = negative_effect = 0
    rows = []

    for s in data.values():
        symbol = s.get("symbol","")
        price = round(s.get("last_price",0),2)
        close = s.get("ohlc",{}).get("close",0)
        rupee = round(s.get("net_change",0),2)
        pct = round((rupee / close) * 100,2) if close else 0
        wt = weights.get(symbol,0)
        effect = round(wt * pct,2)

        if rupee > 0:
            green += 1; total_price_up += rupee; positive_effect += effect
        elif rupee < 0:
            red += 1; total_price_down += rupee; negative_effect += effect

        rows.append({"symbol":symbol,"price":price,"rupee":rupee,"pct":pct,"weight":wt,"effect":effect})

    total_price_up = round(total_price_up,2)
    total_price_down = round(total_price_down,2)
    net_price_change = round(total_price_up + total_price_down,2)
    positive_effect = round(positive_effect,2)
    negative_effect = round(negative_effect,2)
    net_effect = round(positive_effect + negative_effect,2)

    weight_meter = round((positive_effect / (positive_effect + abs(negative_effect))) * 100,1) if (positive_effect + abs(negative_effect)) > 0 else 50
    price_meter = round((total_price_up / (total_price_up + abs(total_price_down))) * 100,1) if (total_price_up + abs(total_price_down)) > 0 else 50

    news = fetch_news()
    nscore = news_score(news)

    final_score = round((weight_meter * 0.55) + (price_meter * 0.25) + (nscore * 0.20),1)

    weight_angle = round(-90 + weight_meter * 1.8,1)
    price_angle = round(-90 + price_meter * 1.8,1)
    news_angle = round(-90 + nscore * 1.8,1)

    buy_pressure = final_score
    sell_pressure = round(100 - final_score,1)

    if final_score >= 70:
        final_decision, color = "STRONG BUY / CALL SIDE", "#d9fbe6"
    elif final_score >= 60:
        final_decision, color = "BUY SIDE WATCH", "#fff3cd"
    elif final_score <= 30:
        final_decision, color = "STRONG SELL / PUT SIDE", "#ffe1e1"
    elif final_score <= 40:
        final_decision, color = "SELL SIDE WATCH", "#fff3cd"
    else:
        final_decision, color = "NO TRADE / SIDEWAYS", "#fff3cd"

    return render_template_string(
        HTML,
        nifty_price=nifty_price,
        weight_meter=weight_meter,
        price_meter=price_meter,
        news_meter=nscore,
        final_score=final_score,
        weight_angle=weight_angle,
        price_angle=price_angle,
        news_angle=news_angle,
        final_decision=final_decision,
        color=color,
        net_price_change=net_price_change,
        net_effect=net_effect,
        green=green,
        red=red,
        buy_pressure=buy_pressure,
        sell_pressure=sell_pressure,
        news_rows=make_news_rows(news),
        rows=make_table(sorted(rows, key=lambda x:x["effect"], reverse=True)),
        time=datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    )
