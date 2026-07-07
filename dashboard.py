from flask import Flask, render_template_string, jsonify
import requests, os
from datetime import datetime

app = Flask(__name__)
TOKEN = os.environ.get("UPSTOX_TOKEN")
UNDERLYING = "NSE_INDEX|Nifty 50"
STRIKE_STEP = 50
AROUND_STRIKES = 10

def h():
    return {"Accept":"application/json","Authorization":"Bearer "+TOKEN}

def fmt(n):
    try:
        n=float(n); s="-" if n<0 else ""; n=abs(n)
        if n>=10000000: return s+str(round(n/10000000,2))+"Cr"
        if n>=100000: return s+str(round(n/100000,2))+"L"
        if n>=1000: return s+str(round(n/1000,1))+"K"
        return s+str(int(n))
    except:
        return "-"

def oi_chg(md):
    for k in ["oi_day_change","oi_change","change_oi","oi_change_value"]:
        if md.get(k) not in [None,""]:
            return float(md.get(k) or 0)
    return 0

def expiry():
    e=os.environ.get("EXPIRY_DATE")
    if e: return e
    r=requests.get(
        "https://api.upstox.com/v2/option/contract",
        headers=h(),
        params={"instrument_key":UNDERLYING},
        timeout=10
    ).json()
    ex=sorted(list(set([x.get("expiry") for x in r.get("data",[]) if x.get("expiry")])))
    if not ex: raise Exception("EXPIRY_DATE add karo")
    return ex[0]

@app.route("/api")
def api():
    if not TOKEN:
        return jsonify({"error":"UPSTOX_TOKEN missing"})

    try:
        l=requests.get(
            "https://api.upstox.com/v2/market-quote/ltp",
            headers=h(),
            params={"instrument_key":UNDERLYING},
            timeout=10
        ).json()
        nifty=float(l["data"]["NSE_INDEX:Nifty 50"]["last_price"])

        exp=expiry()

        oc=requests.get(
            "https://api.upstox.com/v2/option/chain",
            headers=h(),
            params={"instrument_key":UNDERLYING,"expiry_date":exp},
            timeout=15
        ).json()

        data=oc.get("data",[])
    except Exception as e:
        return jsonify({"error":str(e)})

    atm=round(nifty/STRIKE_STEP)*STRIKE_STEP
    low=atm-AROUND_STRIKES*STRIKE_STEP
    high=atm+AROUND_STRIKES*STRIKE_STEP

    rows=[]
    total_call_oi=total_put_oi=0
    total_call_chg=total_put_chg=0

    for x in data:
        strike=int(float(x.get("strike_price",0)))
        if strike<low or strike>high:
            continue

        c=x.get("call_options",{}).get("market_data",{})
        p=x.get("put_options",{}).get("market_data",{})

        coi=float(c.get("oi",0) or 0)
        poi=float(p.get("oi",0) or 0)
        cchg=oi_chg(c)
        pchg=oi_chg(p)

        strike_total_oi = coi + poi
        strike_total_chg = cchg + pchg

        total_call_oi += coi
        total_put_oi += poi
        total_call_chg += cchg
        total_put_chg += pchg

        rows.append({
            "strike":strike,
            "atm":strike==atm,
            "coi":fmt(coi),
            "cchg":fmt(cchg),
            "pchg":fmt(pchg),
            "poi":fmt(poi),
            "total_oi":fmt(strike_total_oi),
            "total_chg":fmt(strike_total_chg),
            "rc":cchg,
            "rp":pchg,
            "rt":strike_total_chg
        })

    rows=sorted(rows,key=lambda x:x["strike"])

    pcr=round(total_put_oi/total_call_oi,2) if total_call_oi else 0

    if total_put_chg > total_call_chg:
        decision="🟢 PUT CHANGE વધારે - CALL SIDE WATCH"
        color="#d9fbe6"
    elif total_call_chg > total_put_chg:
        decision="🔴 CALL CHANGE વધારે - PUT SIDE WATCH"
        color="#ffe1e1"
    else:
        decision="🟡 MIXED / WAIT"
        color="#fff3cd"

    return jsonify({
        "nifty":nifty,
        "atm":atm,
        "expiry":exp,
        "pcr":pcr,
        "decision":decision,
        "color":color,
        "rows":rows,
        "time":datetime.now().strftime("%H:%M:%S")
    })

HTML="""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty Strike Total OI</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0;padding:8px}
.card{background:white;padding:12px;margin:7px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.big{font-size:24px;font-weight:bold}
.signal{padding:15px;border-radius:14px;text-align:center;font-size:21px;font-weight:bold;margin:7px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.box{background:#f8f9fa;border-radius:12px;padding:9px;text-align:center}
.label{font-size:12px;color:#555}
.val{font-size:18px;font-weight:bold}
.green{color:green;font-weight:bold}
.red{color:red;font-weight:bold}
.blue{color:#064fcb;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:11px;background:white}
td,th{padding:6px;border-bottom:1px solid #ddd;text-align:right}
td:first-child,th:first-child{text-align:center}
.atm{background:#fff3cd;font-weight:bold}
.small{text-align:center;color:#555;font-size:12px}
</style>
</head>
<body>

<div class="card">NIFTY LIVE: <span class="big" id="nifty">Loading...</span></div>
<div class="signal" id="decision">Loading...</div>

<div class="card">
<div class="grid">
<div class="box"><div class="label">ATM Strike</div><div class="val" id="atm">-</div></div>
<div class="box"><div class="label">PCR</div><div class="val" id="pcr">-</div></div>
<div class="box"><div class="label">Expiry</div><div class="val" id="expiry">-</div></div>
<div class="box"><div class="label">Updated</div><div class="val" id="time">-</div></div>
</div>
</div>

<div class="card">
<h3>ATM ± 10 Strike OI With Total</h3>
<table>
<thead>
<tr>
<th>Strike</th>
<th>Call OI</th>
<th>Call Chg</th>
<th>Put Chg</th>
<th>Put OI</th>
<th>Total OI</th>
<th>Total Chg</th>
</tr>
</thead>
<tbody id="tbody"></tbody>
</table>
</div>

<p class="small">Auto refresh 2 sec</p>

<script>
async function loadData(){
    let r=await fetch('/api');
    let d=await r.json();

    if(d.error){
        document.getElementById('decision').innerText=d.error;
        document.getElementById('decision').style.background='#ffe1e1';
        return;
    }

    document.getElementById('nifty').innerText=d.nifty;
    document.getElementById('atm').innerText=d.atm;
    document.getElementById('pcr').innerText=d.pcr;
    document.getElementById('expiry').innerText=d.expiry;
    document.getElementById('time').innerText=d.time;
    document.getElementById('decision').innerText=d.decision;
    document.getElementById('decision').style.background=d.color;

    let html='';
    d.rows.forEach(x=>{
        html+=`
        <tr class="${x.atm?'atm':''}">
            <td>${x.strike}</td>
            <td class="red">${x.coi}</td>
            <td class="${x.rc<0?'green':'red'}">${x.cchg}</td>
            <td class="${x.rp>0?'green':'red'}">${x.pchg}</td>
            <td class="green">${x.poi}</td>
            <td class="blue">${x.total_oi}</td>
            <td class="${x.rt>=0?'blue':'red'}">${x.total_chg}</td>
        </tr>`;
    });

    document.getElementById('tbody').innerHTML=html;
}

loadData();
setInterval(loadData,2000);
</script>

</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)
