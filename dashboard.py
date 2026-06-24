from flask import Flask, render_template_string
from markupsafe import Markup
import requests, os
from datetime import datetime

app = Flask(__name__)
TOKEN = os.environ.get("UPSTOX_TOKEN")

stocks = {
"HDFCBANK":"NSE_EQ|INE040A01034","RELIANCE":"NSE_EQ|INE002A01018","ICICIBANK":"NSE_EQ|INE090A01021","BHARTIARTL":"NSE_EQ|INE397D01024","LT":"NSE_EQ|INE018A01030","SBIN":"NSE_EQ|INE062A01020","INFY":"NSE_EQ|INE009A01021","AXISBANK":"NSE_EQ|INE238A01034","ITC":"NSE_EQ|INE154A01025","KOTAKBANK":"NSE_EQ|INE237A01036","M&M":"NSE_EQ|INE101A01026","TCS":"NSE_EQ|INE467B01029","BAJFINANCE":"NSE_EQ|INE296A01032","HINDUNILVR":"NSE_EQ|INE030A01027","SUNPHARMA":"NSE_EQ|INE044A01036","NTPC":"NSE_EQ|INE733E01010","TITAN":"NSE_EQ|INE280A01028","ETERNAL":"NSE_EQ|INE758T01015","TATASTEEL":"NSE_EQ|INE081A01020","MARUTI":"NSE_EQ|INE585B01010","BEL":"NSE_EQ|INE263A01024","HINDALCO":"NSE_EQ|INE038A01020","POWERGRID":"NSE_EQ|INE752E01010","ULTRACEMCO":"NSE_EQ|INE481G01011","HCLTECH":"NSE_EQ|INE860A01027","ADANIPORTS":"NSE_EQ|INE742F01042","JSWSTEEL":"NSE_EQ|INE019A01038","ONGC":"NSE_EQ|INE213A01029","ASIANPAINT":"NSE_EQ|INE021A01026","COALINDIA":"NSE_EQ|INE522F01014","GRASIM":"NSE_EQ|INE047A01021","NESTLEIND":"NSE_EQ|INE239A01024","BAJAJFINSV":"NSE_EQ|INE918I01026","TECHM":"NSE_EQ|INE669C01036","TRENT":"NSE_EQ|INE849A01020","DRREDDY":"NSE_EQ|INE089A01031","CIPLA":"NSE_EQ|INE059A01026","ADANIENT":"NSE_EQ|INE423A01024","WIPRO":"NSE_EQ|INE075A01022"
}

weights = {
"HDFCBANK":10.73,"RELIANCE":8.78,"ICICIBANK":8.21,"BHARTIARTL":5.26,"LT":4.28,"SBIN":4.03,"INFY":3.76,"AXISBANK":3.31,"ITC":2.76,"KOTAKBANK":2.56,"M&M":2.51,"TCS":2.30,"BAJFINANCE":2.28,"HINDUNILVR":1.81,"SUNPHARMA":1.74,"NTPC":1.72,"TITAN":1.64,"ETERNAL":1.62,"TATASTEEL":1.59,"MARUTI":1.59,"BEL":1.40,"HINDALCO":1.37,"POWERGRID":1.31,"ULTRACEMCO":1.25,"HCLTECH":1.15,"ADANIPORTS":1.11,"JSWSTEEL":1.08,"ONGC":1.06,"ASIANPAINT":1.00,"COALINDIA":0.99,"GRASIM":0.97,"NESTLEIND":0.95,"BAJAJFINSV":0.92,"TECHM":0.85,"TRENT":0.84,"DRREDDY":0.73,"CIPLA":0.67,"ADANIENT":0.63,"WIPRO":0.52
}

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>Ultra Pro Nifty</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0;padding:8px}
.card{background:white;padding:12px;margin:7px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.signal{padding:18px;border-radius:16px;text-align:center;font-size:25px;font-weight:bold;margin:7px}
.big{font-size:24px;font-weight:bold}.green{color:green;font-weight:bold}.red{color:red;font-weight:bold}.orange{color:#b36b00;font-weight:bold}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.box{background:#f8f9fa;border-radius:12px;padding:10px;text-align:center}
.label{font-size:12px;color:#555}.val{font-size:20px;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:6px;border-bottom:1px solid #ddd;text-align:left}
input{width:42%;padding:9px;margin:3px;border-radius:8px;border:1px solid #ccc}
button{padding:9px;border:0;border-radius:8px;font-weight:bold;background:#111;color:white}
.small{text-align:center;color:#555;font-size:12px}
</style>
</head>
<body>

<div class="card">NIFTY LIVE: <span class="big">{{ nifty_price }}</span></div>

<div class="signal" style="background:{{ color }}">{{ final_decision }}</div>

<div class="card">
<div class="grid">
<div class="box"><div class="label">Market Power</div><div class="val">{{ market_power }}/100</div></div>
<div class="box"><div class="label">Confidence</div><div class="val">{{ confidence }}%</div></div>
<div class="box"><div class="label">Weight Effect</div><div class="val">{{ net_effect }}</div></div>
<div class="box"><div class="label">Price Effect</div><div class="val">{{ net_price }}</div></div>
<div class="box"><div class="label">Green / Red</div><div class="val"><span class="green">{{ green }}</span> / <span class="red">{{ red }}</span></div></div>
<div class="box"><div class="label">Buy / Sell</div><div class="val"><span class="green">{{ buy }}%</span> / <span class="red">{{ sell }}%</span></div></div>
</div>
</div>

<div class="card">
<h3>Option Data Input</h3>
<input id="pcr" placeholder="PCR e.g. 1.15">
<input id="vix" placeholder="VIX e.g. 12.5"><br>
<input id="callw" placeholder="Call Writing Strike">
<input id="putw" placeholder="Put Writing Strike"><br>
<button onclick="saveOI()">Save OI Data</button>
<div class="small">Saved PCR: <b id="spcr">-</b> | VIX: <b id="svix">-</b> | CallW: <b id="scall">-</b> | PutW: <b id="sput">-</b></div>
</div>

<div class="card">
<h3>Nifty Drivers</h3>
<table><tr><th>Stock</th><th>₹</th><th>%</th><th>Wt</th><th>Effect</th></tr>{{ drivers }}</table>
</div>

<div class="card">
<h3>All Stocks</h3>
<table><tr><th>Stock</th><th>Price</th><th>₹</th><th>%</th><th>Wt</th><th>Effect</th></tr>{{ rows }}</table>
</div>

<p class="small">Auto refresh 5 sec | Updated: {{ time }}</p>

<script>
function saveOI(){
 localStorage.setItem("pcr",document.getElementById("pcr").value);
 localStorage.setItem("vix",document.getElementById("vix").value);
 localStorage.setItem("callw",document.getElementById("callw").value);
 localStorage.setItem("putw",document.getElementById("putw").value);
 loadOI();
}
function loadOI(){
 document.getElementById("spcr").innerText=localStorage.getItem("pcr")||"-";
 document.getElementById("svix").innerText=localStorage.getItem("vix")||"-";
 document.getElementById("scall").innerText=localStorage.getItem("callw")||"-";
 document.getElementById("sput").innerText=localStorage.getItem("putw")||"-";
 document.getElementById("pcr").value=localStorage.getItem("pcr")||"";
 document.getElementById("vix").value=localStorage.getItem("vix")||"";
 document.getElementById("callw").value=localStorage.getItem("callw")||"";
 document.getElementById("putw").value=localStorage.getItem("putw")||"";
}
loadOI();
</script>

</body>
</html>
"""

def table(rows):
    out=""
    for r in rows:
        c="green" if r["effect"]>0 else "red"
        rc="green" if r["rupee"]>0 else "red"
        out+=f"<tr><td>{r['symbol']}</td><td>{r['price']}</td><td class='{rc}'>{r['rupee']}</td><td class='{c}'>{r['pct']}%</td><td>{r['weight']}%</td><td class='{c}'>{r['effect']}</td></tr>"
    return Markup(out)

def driver_table(rows):
    out=""
    for r in rows[:10]:
        c="green" if r["effect"]>0 else "red"
        out+=f"<tr><td>{r['symbol']}</td><td>{r['rupee']}</td><td class='{c}'>{r['pct']}%</td><td>{r['weight']}%</td><td class='{c}'>{r['effect']}</td></tr>"
    return Markup(out)

@app.route("/")
def home():
    if not TOKEN:
        return "UPSTOX_TOKEN missing"

    headers={"Accept":"application/json","Authorization":"Bearer "+TOKEN}

    try:
        n=requests.get("https://api.upstox.com/v2/market-quote/ltp",headers=headers,params={"instrument_key":"NSE_INDEX|Nifty 50"},timeout=10).json()
        nifty_price=n["data"]["NSE_INDEX:Nifty 50"]["last_price"]
    except:
        nifty_price="Error"

    try:
        q=requests.get("https://api.upstox.com/v2/market-quote/quotes",headers=headers,params={"instrument_key":",".join(stocks.values())},timeout=15).json()["data"]
    except Exception as e:
        return "Upstox API Error: "+str(e)

    green=red=0
    pos=neg=0
    rup_up=rup_down=0
    rows=[]

    for s in q.values():
        symbol=s.get("symbol","")
        price=round(s.get("last_price",0),2)
        close=s.get("ohlc",{}).get("close",0)
        rupee=round(s.get("net_change",0),2)
        pct=round((rupee/close)*100,2) if close else 0
        wt=weights.get(symbol,0)
        effect=round(wt*pct,2)

        if rupee>0:
            green+=1; pos+=effect; rup_up+=rupee
        elif rupee<0:
            red+=1; neg+=effect; rup_down+=rupee

        rows.append({"symbol":symbol,"price":price,"rupee":rupee,"pct":pct,"weight":wt,"effect":effect})

    pos=round(pos,2); neg=round(neg,2)
    net_effect=round(pos+neg,2)
    net_price=round(rup_up+rup_down,2)

    total_abs=pos+abs(neg)
    weight_score=round((pos/total_abs)*100,1) if total_abs>0 else 50

    price_abs=rup_up+abs(rup_down)
    price_score=round((rup_up/price_abs)*100,1) if price_abs>0 else 50

    market_power=round((weight_score*0.7)+(price_score*0.3),1)
    buy=market_power
    sell=round(100-market_power,1)
    confidence=round(abs(market_power-50)*2,1)

    if market_power>=70:
        final_decision="✅ CALL BUY - STRONG BULLISH"; color="#d9fbe6"
    elif market_power>=60:
        final_decision="🟢 CALL SIDE WATCH"; color="#fff3cd"
    elif market_power<=30:
        final_decision="✅ PUT BUY - STRONG BEARISH"; color="#ffe1e1"
    elif market_power<=40:
        final_decision="🔴 PUT SIDE WATCH"; color="#fff3cd"
    else:
        final_decision="⚠ NO TRADE / SIDEWAYS"; color="#fff3cd"

    rows_sorted=sorted(rows,key=lambda x:abs(x["effect"]),reverse=True)

    return render_template_string(
        HTML,
        nifty_price=nifty_price,
        final_decision=final_decision,
        color=color,
        market_power=market_power,
        confidence=confidence,
        net_effect=net_effect,
        net_price=net_price,
        green=green,
        red=red,
        buy=buy,
        sell=sell,
        drivers=driver_table(rows_sorted),
        rows=table(sorted(rows,key=lambda x:x["effect"],reverse=True)),
        time=datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    )
