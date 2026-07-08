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
    for k in ["oi_day_change","oi_change","change_oi","oi_change_value","change_in_oi"]:
        v=md.get(k)
        if v not in [None,""]:
            return float(v or 0)
    oi=float(md.get("oi",0) or 0)
    prev=float(md.get("previous_oi",0) or md.get("prev_oi",0) or md.get("close_oi",0) or 0)
    return oi-prev if prev else 0

def expiry():
    e=os.environ.get("EXPIRY_DATE")
    if e: return e
    r=requests.get("https://api.upstox.com/v2/option/contract",headers=h(),params={"instrument_key":UNDERLYING},timeout=10).json()
    ex=sorted(list(set([x.get("expiry") for x in r.get("data",[]) if x.get("expiry")])))
    if not ex: raise Exception("EXPIRY_DATE Render Environment ma add karo")
    return ex[0]

@app.route("/api")
def api():
    if not TOKEN: return jsonify({"error":"UPSTOX_TOKEN missing"})
    try:
        l=requests.get("https://api.upstox.com/v2/market-quote/ltp",headers=h(),params={"instrument_key":UNDERLYING},timeout=10).json()
        nifty=float(l["data"]["NSE_INDEX:Nifty 50"]["last_price"])
        exp=expiry()
        oc=requests.get("https://api.upstox.com/v2/option/chain",headers=h(),params={"instrument_key":UNDERLYING,"expiry_date":exp},timeout=15).json()
        data=oc.get("data",[])
    except Exception as e:
        return jsonify({"error":str(e)})

    atm=round(nifty/STRIKE_STEP)*STRIKE_STEP
    low=atm-AROUND_STRIKES*STRIKE_STEP
    high=atm+AROUND_STRIKES*STRIKE_STEP

    rows=[]
    sum_call_total=0
    sum_put_total=0

    for x in data:
        strike=int(float(x.get("strike_price",0)))
        if strike<low or strike>high: continue

        c=x.get("call_options",{}).get("market_data",{})
        p=x.get("put_options",{}).get("market_data",{})

        call_oi=float(c.get("oi",0) or 0)
        put_oi=float(p.get("oi",0) or 0)
        call_chg=oi_chg(c)
        put_chg=oi_chg(p)

        call_total=call_oi+call_chg
        put_total=put_oi+put_chg
        diff=put_total-call_total

        sum_call_total+=call_total
        sum_put_total+=put_total

        rows.append({
            "strike":strike,
            "atm":strike==atm,
            "call_oi":fmt(call_oi),
            "call_chg":fmt(call_chg),
            "call_total":fmt(call_total),
            "put_oi":fmt(put_oi),
            "put_chg":fmt(put_chg),
            "put_total":fmt(put_total),
            "diff":fmt(diff),
            "call_total_raw":call_total,
            "put_total_raw":put_total,
            "diff_raw":diff,
            "call_chg_raw":call_chg,
            "put_chg_raw":put_chg
        })

    rows=sorted(rows,key=lambda x:x["strike"])
    final_diff=sum_put_total-sum_call_total

    if final_diff>0:
        decision="🟢 PUT TOTAL વધારે - CALL SIDE WATCH"
        color="#d9fbe6"
    elif final_diff<0:
        decision="🔴 CALL TOTAL વધારે - PUT SIDE WATCH"
        color="#ffe1e1"
    else:
        decision="🟡 SAME / WAIT"
        color="#fff3cd"

    return jsonify({
        "nifty":nifty,
        "atm":atm,
        "expiry":exp,
        "decision":decision,
        "color":color,
        "sum_call_total":fmt(sum_call_total),
        "sum_put_total":fmt(sum_put_total),
        "final_diff":fmt(final_diff),
        "rows":rows,
        "time":datetime.now().strftime("%H:%M:%S")
    })

HTML="""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty Live OI Flow</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0;padding:8px}
.card{background:white;padding:12px;margin:7px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.big{font-size:24px;font-weight:bold}.signal{padding:15px;border-radius:14px;text-align:center;font-size:21px;font-weight:bold;margin:7px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.box{background:#f8f9fa;border-radius:12px;padding:9px;text-align:center}
.label{font-size:12px;color:#555}.val{font-size:18px;font-weight:bold}
.green{color:green;font-weight:bold}.red{color:red;font-weight:bold}.blue{color:#064fcb;font-weight:bold}
.high{background:#d9fbe6!important;color:green!important;font-weight:bold}
.drop{background:#ffe1e1!important;color:red!important;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:10.5px;background:white}
td,th{padding:5px;border-bottom:1px solid #ddd;text-align:right}
td:first-child,th:first-child{text-align:center}.atm{background:#fff3cd;font-weight:bold}
.small{text-align:center;color:#555;font-size:12px}
</style>
</head>
<body>

<div class="card">NIFTY LIVE: <span class="big" id="nifty">Loading...</span></div>
<div class="signal" id="decision">Loading...</div>

<div class="card">
<div class="grid">
<div class="box"><div class="label">ATM</div><div class="val" id="atm">-</div></div>
<div class="box"><div class="label">Updated</div><div class="val" id="time">-</div></div>
<div class="box"><div class="label">Call Total Sum</div><div class="val red" id="sum_call_total">-</div></div>
<div class="box"><div class="label">Put Total Sum</div><div class="val green" id="sum_put_total">-</div></div>
<div class="box"><div class="label">Put - Call Diff</div><div class="val blue" id="final_diff">-</div></div>
<div class="box"><div class="label">Live Flow</div><div class="val" id="flow">Waiting...</div></div>
</div>
</div>

<div class="card">
<h3>Live Strike Flow</h3>
<table>
<thead>
<tr>
<th>Strike</th>
<th>Call Total</th>
<th>Call Flow</th>
<th>Put Flow</th>
<th>Put Total</th>
<th>Diff</th>
</tr>
</thead>
<tbody id="tbody"></tbody>
</table>
</div>

<p class="small">Auto refresh 2 sec | Flow = last refresh થી change</p>

<script>
let previous = {};

function f(n){
    if(n===0 || !n) return "0";
    let s = n>0 ? "+" : "-";
    n = Math.abs(n);
    if(n>=10000000) return s+(n/10000000).toFixed(2)+"Cr";
    if(n>=100000) return s+(n/100000).toFixed(2)+"L";
    if(n>=1000) return s+(n/1000).toFixed(1)+"K";
    return s+Math.round(n);
}

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
    document.getElementById('time').innerText=d.time;
    document.getElementById('decision').innerText=d.decision;
    document.getElementById('decision').style.background=d.color;
    document.getElementById('sum_call_total').innerText=d.sum_call_total;
    document.getElementById('sum_put_total').innerText=d.sum_put_total;
    document.getElementById('final_diff').innerText=d.final_diff;

    let totalCallFlow=0, totalPutFlow=0;
    let html='';

    d.rows.forEach(x=>{
        let old=previous[x.strike] || {call: x.call_total_raw, put: x.put_total_raw};
        let callFlow=x.call_total_raw-old.call;
        let putFlow=x.put_total_raw-old.put;

        totalCallFlow += callFlow;
        totalPutFlow += putFlow;

        let callCls = callFlow>0 ? "drop" : (callFlow<0 ? "high" : "red");
        let putCls = putFlow>0 ? "high" : (putFlow<0 ? "drop" : "green");

        html+=`
        <tr class="${x.atm?'atm':''}">
            <td>${x.strike}</td>
            <td class="red">${x.call_total}</td>
            <td class="${callCls}">${f(callFlow)}</td>
            <td class="${putCls}">${f(putFlow)}</td>
            <td class="green">${x.put_total}</td>
            <td class="${x.diff_raw>=0?'green':'red'}">${x.diff}</td>
        </tr>`;

        previous[x.strike] = {call:x.call_total_raw, put:x.put_total_raw};
    });

    document.getElementById('tbody').innerHTML=html;

    let flowText="";
    if(totalPutFlow > totalCallFlow){
        flowText="🟢 Put Flow Strong";
        document.getElementById('flow').className="val green";
    }else if(totalCallFlow > totalPutFlow){
        flowText="🔴 Call Flow Strong";
        document.getElementById('flow').className="val red";
    }else{
        flowText="🟡 Mixed";
        document.getElementById('flow').className="val";
    }
    document.getElementById('flow').innerText=flowText;
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
