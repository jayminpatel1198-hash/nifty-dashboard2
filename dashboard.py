from flask import Flask, render_template_string, request, jsonify
from markupsafe import Markup
import requests, os
from datetime import datetime, timedelta
from urllib.parse import quote

app = Flask(__name__)
TOKEN = os.environ.get("UPSTOX_TOKEN")

instruments = {
"HDFCBANK":"NSE_EQ|INE040A01034","RELIANCE":"NSE_EQ|INE002A01018","ICICIBANK":"NSE_EQ|INE090A01021","SBIN":"NSE_EQ|INE062A01020","KOTAKBANK":"NSE_EQ|INE237A01036","AXISBANK":"NSE_EQ|INE238A01034","INDUSINDBK":"NSE_EQ|INE095A01012","BANKBARODA":"NSE_EQ|INE028A01039","PNB":"NSE_EQ|INE160A01022","CANBK":"NSE_EQ|INE476A01014","FEDERALBNK":"NSE_EQ|INE171A01029","IDFCFIRSTB":"NSE_EQ|INE092T01019","AUBANK":"NSE_EQ|INE949L01017",
"BHARTIARTL":"NSE_EQ|INE397D01024","LT":"NSE_EQ|INE018A01030","INFY":"NSE_EQ|INE009A01021","ITC":"NSE_EQ|INE154A01025","M&M":"NSE_EQ|INE101A01026","TCS":"NSE_EQ|INE467B01029","BAJFINANCE":"NSE_EQ|INE296A01032","HINDUNILVR":"NSE_EQ|INE030A01027","SUNPHARMA":"NSE_EQ|INE044A01036","NTPC":"NSE_EQ|INE733E01010","TITAN":"NSE_EQ|INE280A01028","TATASTEEL":"NSE_EQ|INE081A01020","MARUTI":"NSE_EQ|INE585B01010","BEL":"NSE_EQ|INE263A01024","HINDALCO":"NSE_EQ|INE038A01020","POWERGRID":"NSE_EQ|INE752E01010","ULTRACEMCO":"NSE_EQ|INE481G01011","HCLTECH":"NSE_EQ|INE860A01027","ADANIPORTS":"NSE_EQ|INE742F01042","JSWSTEEL":"NSE_EQ|INE019A01038","ONGC":"NSE_EQ|INE213A01029","ASIANPAINT":"NSE_EQ|INE021A01026","COALINDIA":"NSE_EQ|INE522F01014","GRASIM":"NSE_EQ|INE047A01021","NESTLEIND":"NSE_EQ|INE239A01024","BAJAJFINSV":"NSE_EQ|INE918I01026","TECHM":"NSE_EQ|INE669C01036","TRENT":"NSE_EQ|INE849A01020","DRREDDY":"NSE_EQ|INE089A01031","CIPLA":"NSE_EQ|INE059A01026","ADANIENT":"NSE_EQ|INE423A01024","WIPRO":"NSE_EQ|INE075A01022"
}

nifty_weights = {"HDFCBANK":10.73,"RELIANCE":8.78,"ICICIBANK":8.21,"BHARTIARTL":5.26,"LT":4.28,"SBIN":4.03,"INFY":3.76,"AXISBANK":3.31,"ITC":2.76,"KOTAKBANK":2.56,"M&M":2.51,"TCS":2.30,"BAJFINANCE":2.28,"HINDUNILVR":1.81,"SUNPHARMA":1.74,"NTPC":1.72,"TITAN":1.64,"TATASTEEL":1.59,"MARUTI":1.59,"BEL":1.40,"HINDALCO":1.37,"POWERGRID":1.31,"ULTRACEMCO":1.25,"HCLTECH":1.15,"ADANIPORTS":1.11,"JSWSTEEL":1.08,"ONGC":1.06,"ASIANPAINT":1.00,"COALINDIA":0.99,"GRASIM":0.97,"NESTLEIND":0.95,"BAJAJFINSV":0.92,"TECHM":0.85,"TRENT":0.84,"DRREDDY":0.73,"CIPLA":0.67,"ADANIENT":0.63,"WIPRO":0.52}

bank_weights = {"HDFCBANK":28,"ICICIBANK":24,"SBIN":11,"KOTAKBANK":10,"AXISBANK":9,"INDUSINDBK":5,"BANKBARODA":4,"PNB":3,"CANBK":2.5,"FEDERALBNK":1.5,"IDFCFIRSTB":1,"AUBANK":1}

configs = {
"NIFTY":{"title":"NIFTY 50","index_key":"NSE_INDEX|Nifty 50","weights":nifty_weights},
"BANKNIFTY":{"title":"BANKNIFTY","index_key":"NSE_INDEX|Nifty Bank","weights":bank_weights},
"SENSEX":{"title":"SENSEX","index_key":"BSE_INDEX|SENSEX","weights":{}}
}

def auth_headers():
    return {"Accept":"application/json","Authorization":"Bearer " + TOKEN}

@app.route("/candles")
def candles():
    idx = request.args.get("index","NIFTY").upper()
    tf = request.args.get("tf","5M")
    if idx not in configs:
        idx = "NIFTY"

    key = quote(configs[idx]["index_key"], safe="")
    today = datetime.now().date()

    try:
        if tf == "5M":
            url = f"https://api.upstox.com/v3/historical-candle/intraday/{key}/minutes/5"
        elif tf == "1H":
            url = f"https://api.upstox.com/v3/historical-candle/{key}/hours/1/{today}/{today-timedelta(days=30)}"
        elif tf == "1D":
            url = f"https://api.upstox.com/v3/historical-candle/{key}/days/1/{today}/{today-timedelta(days=365)}"
        else:
            url = f"https://api.upstox.com/v3/historical-candle/intraday/{key}/minutes/5"

        js = requests.get(url, headers=auth_headers(), timeout=20).json()
        raw = js.get("data",{}).get("candles",[])

        out = []
        for c in raw:
            out.append({
                "time": int(datetime.fromisoformat(c[0].replace("Z","+00:00")).timestamp()),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4])
            })

        return jsonify({"candles": list(reversed(out))})
    except Exception as e:
        return jsonify({"error": str(e)})

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} Dashboard</title>
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<style>
body{font-family:Arial;background:#f4f6f8;padding:12px;margin:0}
h2{text-align:center}.card{background:white;padding:14px;margin:8px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.signal{padding:18px;border-radius:16px;text-align:center;font-size:23px;font-weight:bold;margin:8px}
.big{font-size:23px;font-weight:bold}.green{color:green;font-weight:bold}.red{color:red;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:7px;border-bottom:1px solid #ddd;text-align:left}
select{font-size:18px;padding:10px;border-radius:10px;width:100%}.small{text-align:center;color:#555}
button{padding:9px;margin:3px;border:0;border-radius:8px;background:#e8eaed;font-weight:bold}
button.active{background:#111;color:white}
input{padding:10px;border-radius:8px;border:1px solid #ccc;width:38%;margin:3px}
.chartbox{height:540px}
@media (orientation:landscape){.chartbox{height:430px}}
.meterbox{text-align:center}.gauge{width:280px;height:170px;margin:15px auto;position:relative;overflow:hidden}
.gauge:before{content:"";position:absolute;left:20px;top:20px;width:240px;height:240px;border-radius:50%;background:conic-gradient(from 270deg,#d93025 0deg 80deg,#fbbc04 80deg 100deg,#0a9f45 100deg 180deg,transparent 180deg 360deg)}
.gauge:after{content:"";position:absolute;left:60px;top:60px;width:160px;height:160px;background:white;border-radius:50%}
.needle{position:absolute;left:138px;top:130px;width:5px;height:105px;background:#111;transform-origin:2.5px 2.5px;z-index:3;border-radius:5px}
.center{position:absolute;left:126px;top:118px;width:29px;height:29px;background:#111;border-radius:50%;z-index:4}
.score{position:absolute;left:0;right:0;top:98px;text-align:center;font-size:31px;font-weight:bold;z-index:5}
.tick{position:absolute;font-size:13px;font-weight:bold;z-index:6}
.t10{left:18px;top:126px}.t20{left:30px;top:88px}.t30{left:58px;top:54px}.t40{left:96px;top:31px}.t50{left:132px;top:22px}.t60{left:172px;top:31px}.t70{left:207px;top:54px}.t80{left:235px;top:88px}.t90{left:247px;top:126px}.t100{left:230px;top:148px}
.labels{display:flex;justify-content:space-between;font-size:13px;margin:0 18px}
</style>
</head>
<body>
<h2>{{ title }} DASHBOARD</h2>

<div class="card">
<select onchange="changeIndex(this.value)">
<option value="NIFTY" {% if selected=="NIFTY" %}selected{% endif %}>NIFTY 50</option>
<option value="BANKNIFTY" {% if selected=="BANKNIFTY" %}selected{% endif %}>BANKNIFTY</option>
<option value="SENSEX" {% if selected=="SENSEX" %}selected{% endif %}>SENSEX</option>
</select>
</div>

<div class="card">{{ title }} Live: <span class="big">{{ index_price }}</span></div>
<div class="signal" style="background:{{ color }}">{{ final_decision }}</div>

<div class="card">
<h3>{{ title }} Candlestick Chart</h3>
<button onclick="loadChart('5M')" class="active">5 Min</button>
<button onclick="loadChart('1H')">1 Hour</button>
<button onclick="loadChart('1D')">1 Day</button>
<p id="status" class="small">Loading...</p>
<div id="chart" class="chartbox"></div>
</div>

<div class="card">
<h3>Saved Support / Resistance</h3>
<input id="supportInput" placeholder="Support price"><button onclick="saveSupport()">Save Support</button><br>
<input id="resistanceInput" placeholder="Resistance price"><button onclick="saveResistance()">Save Resistance</button><br><br>
Saved Support: <span class="big green" id="savedSupport">-</span><br>
Saved Resistance: <span class="big red" id="savedResistance">-</span><br><br>
<button onclick="clearSR()">Clear Saved Levels</button>
</div>

{% if analysis %}
<div class="card meterbox"><h3>Weightage Impact Meter</h3><div class="gauge">
<div class="tick t10">10</div><div class="tick t20">20</div><div class="tick t30">30</div><div class="tick t40">40</div><div class="tick t50">50</div><div class="tick t60">60</div><div class="tick t70">70</div><div class="tick t80">80</div><div class="tick t90">90</div><div class="tick t100">100</div>
<div class="needle" style="transform:rotate({{ weight_angle }}deg)"></div><div class="center"></div><div class="score">{{ weight_meter }}</div></div>
<div class="labels"><span>Bearish</span><span>50</span><span>Bullish</span></div></div>

<div class="card meterbox"><h3>Price Movement Meter</h3><div class="gauge">
<div class="tick t10">10</div><div class="tick t20">20</div><div class="tick t30">30</div><div class="tick t40">40</div><div class="tick t50">50</div><div class="tick t60">60</div><div class="tick t70">70</div><div class="tick t80">80</div><div class="tick t90">90</div><div class="tick t100">100</div>
<div class="needle" style="transform:rotate({{ price_angle }}deg)"></div><div class="center"></div><div class="score">{{ price_meter }}</div></div>
<div class="labels"><span>Bearish</span><span>50</span><span>Bullish</span></div></div>

<div class="card">Direction: <span class="big">{{ direction }}</span></div>
<div class="card">Green: <span class="big green">{{ green }} ({{ green_pct }}%)</span></div>
<div class="card">Red: <span class="big red">{{ red }} ({{ red_pct }}%)</span></div>
<div class="card">Net Impact: <span class="big">{{ net_impact }}</span></div>
<div class="card">Call Pressure: <span class="big green">{{ call_pressure }}%</span></div>
<div class="card">Put Pressure: <span class="big red">{{ put_pressure }}%</span></div>
<div class="card">Entry Advice: <span class="big">{{ entry_advice }}</span></div>

<div class="card"><h3>Top Pullers</h3><table><tr><th>Stock</th><th>Price</th><th>₹</th><th>%</th><th>Wt</th><th>Impact</th></tr>{{ pullers }}</table></div>
<div class="card"><h3>Top Draggers</h3><table><tr><th>Stock</th><th>Price</th><th>₹</th><th>%</th><th>Wt</th><th>Impact</th></tr>{{ draggers }}</table></div>
{% else %}
<div class="card">SENSEX માટે chart + saved support/resistance છે.</div>
{% endif %}

<p class="small">Updated: {{ time }}</p>

<script>
const selectedIndex = "{{ selected }}";
function changeIndex(v){ window.location.href="/?index="+v; }

let chart = LightweightCharts.createChart(document.getElementById('chart'), {
    layout:{background:{color:'#ffffff'},textColor:'#222'},
    grid:{vertLines:{color:'#eee'},horzLines:{color:'#eee'}},
    timeScale:{timeVisible:true,secondsVisible:false},
    rightPriceScale:{borderVisible:false}
});
let candleSeries = chart.addCandlestickSeries();
let supportLine = null, resistanceLine = null;

function setActive(tf){
 document.querySelectorAll("button").forEach(b=>b.classList.remove("active"));
 document.querySelectorAll("button").forEach(b=>{if(b.innerText==="5 Min" && tf==="5M")b.classList.add("active");if(b.innerText==="1 Hour" && tf==="1H")b.classList.add("active");if(b.innerText==="1 Day" && tf==="1D")b.classList.add("active");});
}
function drawSavedLines(){
 let sup = localStorage.getItem(selectedIndex+"_support");
 let res = localStorage.getItem(selectedIndex+"_resistance");
 document.getElementById("savedSupport").innerText = sup ? sup : "-";
 document.getElementById("savedResistance").innerText = res ? res : "-";
 document.getElementById("supportInput").value = sup ? sup : "";
 document.getElementById("resistanceInput").value = res ? res : "";
 if(supportLine){ candleSeries.removePriceLine(supportLine); supportLine=null; }
 if(resistanceLine){ candleSeries.removePriceLine(resistanceLine); resistanceLine=null; }
 if(sup){ supportLine = candleSeries.createPriceLine({price:Number(sup),color:"green",lineWidth:3,axisLabelVisible:true,title:"Support"}); }
 if(res){ resistanceLine = candleSeries.createPriceLine({price:Number(res),color:"red",lineWidth:3,axisLabelVisible:true,title:"Resistance"}); }
}
function saveSupport(){ let v=document.getElementById("supportInput").value; if(v){localStorage.setItem(selectedIndex+"_support",v); drawSavedLines();} }
function saveResistance(){ let v=document.getElementById("resistanceInput").value; if(v){localStorage.setItem(selectedIndex+"_resistance",v); drawSavedLines();} }
function clearSR(){ localStorage.removeItem(selectedIndex+"_support"); localStorage.removeItem(selectedIndex+"_resistance"); drawSavedLines(); }
function loadChart(tf){
 setActive(tf);
 document.getElementById("status").innerText="Loading "+tf+"...";
 fetch("/candles?index="+selectedIndex+"&tf="+tf)
 .then(r=>r.json()).then(d=>{
   if(d.error){document.getElementById("status").innerText="Error: "+d.error;return;}
   candleSeries.setData(d.candles);
   chart.timeScale().fitContent();
   drawSavedLines();
   document.getElementById("status").innerText=tf+" candles: "+d.candles.length;
 }).catch(e=>{document.getElementById("status").innerText="Chart failed";});
}
loadChart("5M");
</script>
</body>
</html>
"""

def make_rows(items):
    out=""
    for r in items:
        cls="green" if r["impact"]>0 else "red"
        rc="green" if r["rupee"]>0 else "red"
        out += f"<tr><td>{r['symbol']}</td><td>{r['price']}</td><td class='{rc}'>{r['rupee']}</td><td class='{cls}'>{r['pct']}%</td><td>{r['weight']}%</td><td class='{cls}'>{r['impact']}</td></tr>"
    return Markup(out)

@app.route("/")
def home():
    selected=request.args.get("index","NIFTY").upper()
    if selected not in configs:
        selected="NIFTY"
    cfg=configs[selected]
    if not TOKEN:
        return "UPSTOX_TOKEN missing"

    try:
        idx=requests.get("https://api.upstox.com/v2/market-quote/ltp",headers=auth_headers(),params={"instrument_key":cfg["index_key"]},timeout=10).json()
        index_price=list(idx["data"].values())[0]["last_price"]
    except:
        index_price="Error"

    analysis = bool(cfg["weights"])
    if not analysis:
        return render_template_string(HTML, selected=selected,title=cfg["title"],index_price=index_price,analysis=False,time=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),final_decision="CHART MODE",color="#fff3cd",weight_meter=50,price_meter=50,weight_angle=0,price_angle=0,direction="",green=0,red=0,green_pct=0,red_pct=0,net_impact=0,call_pressure=0,put_pressure=0,entry_advice="",pullers=Markup(""),draggers=Markup(""))

    weights=cfg["weights"]
    keys=[instruments[s] for s in weights if s in instruments]

    try:
        data=requests.get("https://api.upstox.com/v2/market-quote/quotes",headers=auth_headers(),params={"instrument_key":",".join(keys)},timeout=15).json()["data"]
    except Exception as e:
        return "Upstox API Error: " + str(e)

    green=red=flat=0
    total_plus=total_minus=pos_imp=neg_imp=0
    rows=[]
    for s in data.values():
        symbol=s.get("symbol","")
        price=round(s.get("last_price",0),2)
        close=s.get("ohlc",{}).get("close",0)
        rupee=round(s.get("net_change",0),2)
        pct=round((rupee/close)*100,2) if close else 0
        wt=weights.get(symbol,0)
        impact=round(wt*pct,2)
        if rupee>0:
            green+=1; total_plus+=rupee; pos_imp+=impact
        elif rupee<0:
            red+=1; total_minus+=rupee; neg_imp+=impact
        else:
            flat+=1
        rows.append({"symbol":symbol,"price":price,"rupee":rupee,"pct":pct,"weight":wt,"impact":impact})

    total=green+red+flat
    green_pct=round(green*100/total,1) if total else 0
    red_pct=round(red*100/total,1) if total else 0
    pos_imp=round(pos_imp,2); neg_imp=round(neg_imp,2)
    net_impact=round(pos_imp+neg_imp,2)
    impact_total=pos_imp+abs(neg_imp)
    weight_meter=round((pos_imp/impact_total)*100,1) if impact_total>0 else 50
    rupee_total=total_plus+abs(total_minus)
    price_meter=round((total_plus/rupee_total)*100,1) if rupee_total>0 else 50
    weight_angle=round(-90+weight_meter*1.8,1)
    price_angle=round(-90+price_meter*1.8,1)
    call_pressure=weight_meter
    put_pressure=round(100-weight_meter,1)

    if weight_meter>=65:
        final_decision,direction,entry_advice,color="CALL SIDE BULLISH","BULLISH","Call after breakout only","#d9fbe6"
    elif weight_meter<=35:
        final_decision,direction,entry_advice,color="PUT SIDE BEARISH","BEARISH","Put after breakdown only","#ffe1e1"
    else:
        final_decision,direction,entry_advice,color="NO TRADE / SIDEWAYS","CHOPPY","Avoid option buying","#fff3cd"

    pullers=sorted([r for r in rows if r["impact"]>0],key=lambda x:x["impact"],reverse=True)[:10]
    draggers=sorted([r for r in rows if r["impact"]<0],key=lambda x:x["impact"])[:10]

    return render_template_string(HTML, selected=selected,title=cfg["title"],index_price=index_price,analysis=True,time=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),final_decision=final_decision,color=color,weight_meter=weight_meter,price_meter=price_meter,weight_angle=weight_angle,price_angle=price_angle,direction=direction,green=green,red=red,green_pct=green_pct,red_pct=red_pct,net_impact=net_impact,call_pressure=call_pressure,put_pressure=put_pressure,entry_advice=entry_advice,pullers=make_rows(pullers),draggers=make_rows(draggers))
