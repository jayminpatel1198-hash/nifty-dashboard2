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
    r=requests.get("https://api.upstox.com/v2/option/contract",headers=h(),params={"instrument_key":UNDERLYING},timeout=10).json()
    ex=sorted(list(set([x.get("expiry") for x in r.get("data",[]) if x.get("expiry")])))
    if not ex: raise Exception("EXPIRY_DATE add karo")
    return ex[0]

@app.route("/api")
def api():
    if not TOKEN:
        return jsonify({"error":"UPSTOX_TOKEN missing"})

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
        if strike<low or strike>high:
            continue

        c=x.get("call_options",{}).get("market_data",{})
        p=x.get("put_options",{}).get("market_data",{})

        call_oi=float(c.get("oi",0) or 0)
        put_oi=float(p.get("oi",0) or 0)
        call_chg=oi_chg(c)
        put_chg=oi_chg(p)

        call_total=call_oi + call_chg
        put_total=put_oi + put_chg
        diff=put_total - call_total

        sum_call_total += call_total
        sum_put_total += put_total

        rows.append({
            "strike":strike,
            "atm":strike==atm,
            "call_oi_raw":call_oi,
            "call_chg_raw":call_chg,
            "put_oi_raw":put_oi,
            "put_chg_raw":put_chg,
            "call_oi":fmt(call_oi),
            "call_chg":fmt(call_chg),
            "call_total":fmt(call_total),
            "put_oi":fmt(put_oi),
            "put_chg":fmt(put_chg),
            "put_total":fmt(put_total),
            "diff":fmt(diff),
            "raw_diff":diff
        })

    rows=sorted(rows,key=lambda x:x["strike"])

    if rows:
        max_call_oi=max([r["call_oi_raw"] for r in rows])
        max_call_chg=max([r["call_chg_raw"] for r in rows])
        max_put_oi=max([r["put_oi_raw"] for r in rows])
        max_put_chg=max([r["put_chg_raw"] for r in rows])
    else:
        max_call_oi=max_call_chg=max_put_oi=max_put_chg=0

    for r in rows:
        r["max_call_oi"] = r["call_oi_raw"] == max_call_oi and max_call_oi > 0
        r["max_call_chg"] = r["call_chg_raw"] == max_call_chg and max_call_chg > 0
        r["max_put_oi"] = r["put_oi_raw"] == max_put_oi and max_put_oi > 0
        r["max_put_chg"] = r["put_chg_raw"] == max_put_chg and max_put_chg > 0

    final_diff=sum_put_total-sum_call_total

    if final_diff > 0:
        decision="🟢 PUT TOTAL વધારે - CALL SIDE WATCH"
        color="#d9fbe6"
    elif final_diff < 0:
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
<title>Nifty OI Total</title>
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
.high{background:#d9fbe6!important;color:green!important;font-weight:bold;border-radius:6px}
table{width:100%;border-collapse:collapse;font-size:10.5px;background:white}
td,th{padding:5px;border-bottom:1px solid #ddd;text-align:right}
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
<div class="box"><div class="label">Expiry</div><div class="val" id="expiry">-</div></div>
<div class="box"><div class="label">Call Total Sum</div><div class="val red" id="sum_call_total">-</div></div>
<div class="box"><div class="label">Put Total Sum</div><div class="val green" id="sum_put_total">-</div></div>
<div class="box"><div class="label">Put - Call Difference</div><div class="val blue" id="final_diff">-</div></div>
<div class="box"><div class="label">Updated</div><div class="val" id="time">-</div></div>
</div>
</div>

<div class="card">
<h3>ATM ± 10 Strike OI Total</h3>
<table>
<thead>
<tr>
<th>Strike</th>
<th>Call OI</th>
<th>Call Chg</th>
<th>Call Total</th>
<th>Put OI</th>
<th>Put Chg</th>
<th>Put Total</th>
<th>Diff</th>
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
    document.getElementById('expiry').innerText=d.expiry;
    document.getElementById('decision').innerText=d.decision;
    document.getElementById('decision').style.background=d.color;
    document.getElementById('sum_call_total').innerText=d.sum_call_total;
    document.getElementById('sum_put_total').innerText=d.sum_put_total;
    document.getElementById('final_diff').innerText=d.final_diff;
    document.getElementById('time').innerText=d.time;

    let html='';
    d.rows.forEach(x=>{
        html+=`
        <tr class="${x.atm?'atm':''}">
            <td>${x.strike}</td>
            <td class="${x.max_call_oi?'high':'red'}">${x.call_oi}</td>
            <td class="${x.max_call_chg?'high':(x.call_chg_raw<0?'green':'red')}">${x.call_chg}</td>
            <td class="red">${x.call_total}</td>
            <td class="${x.max_put_oi?'high':'green'}">${x.put_oi}</td>
            <td class="${x.max_put_chg?'high':(x.put_chg_raw>0?'green':'red')}">${x.put_chg}</td>
            <td class="green">${x.put_total}</td>
            <td class="${x.raw_diff>=0?'green':'red'}">${x.diff}</td>
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
