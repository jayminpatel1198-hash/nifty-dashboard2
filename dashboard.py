from flask import Flask, render_template_string, jsonify
import requests, os
from datetime import datetime

app = Flask(__name__)
TOKEN = os.environ.get("UPSTOX_TOKEN")

UNDERLYING = "NSE_INDEX|Nifty 50"
STRIKE_STEP = 50
AROUND_STRIKES = 10

def h():
    return {"Accept": "application/json", "Authorization": "Bearer " + TOKEN}

def fmt(n):
    try:
        n = float(n)
        sign = "+" if n > 0 else "-" if n < 0 else ""
        n = abs(n)
        if n >= 10000000: return sign + str(round(n/10000000,2)) + "Cr"
        if n >= 100000: return sign + str(round(n/100000,2)) + "L"
        if n >= 1000: return sign + str(round(n/1000,1)) + "K"
        return sign + str(int(n))
    except:
        return "-"

def oi_chg(md):
    for k in ["oi_day_change","oi_change","change_oi","oi_change_value","change_in_oi"]:
        v = md.get(k)
        if v not in [None, ""]:
            return float(v or 0)

    oi = float(md.get("oi",0) or 0)
    prev = float(md.get("previous_oi",0) or md.get("prev_oi",0) or md.get("close_oi",0) or 0)
    return oi - prev if prev else 0

def get_expiry():
    e = os.environ.get("EXPIRY_DATE")
    if e:
        return e

    r = requests.get(
        "https://api.upstox.com/v2/option/contract",
        headers=h(),
        params={"instrument_key": UNDERLYING},
        timeout=10
    ).json()

    ex = sorted(list(set([x.get("expiry") for x in r.get("data", []) if x.get("expiry")])))
    if not ex:
        raise Exception("EXPIRY_DATE Render Environment ma add karo")
    return ex[0]

@app.route("/api")
def api():
    if not TOKEN:
        return jsonify({"error": "UPSTOX_TOKEN missing"})

    try:
        ltp = requests.get(
            "https://api.upstox.com/v2/market-quote/ltp",
            headers=h(),
            params={"instrument_key": UNDERLYING},
            timeout=10
        ).json()

        nifty = float(ltp["data"]["NSE_INDEX:Nifty 50"]["last_price"])
        expiry = get_expiry()

        oc = requests.get(
            "https://api.upstox.com/v2/option/chain",
            headers=h(),
            params={"instrument_key": UNDERLYING, "expiry_date": expiry},
            timeout=15
        ).json()

        data = oc.get("data", [])

    except Exception as e:
        return jsonify({"error": str(e)})

    atm = round(nifty / STRIKE_STEP) * STRIKE_STEP
    low = atm - AROUND_STRIKES * STRIKE_STEP
    high = atm + AROUND_STRIKES * STRIKE_STEP

    rows = []
    total_call_flow = 0
    total_put_flow = 0
    total_call_oi = 0
    total_put_oi = 0

    for x in data:
        strike = int(float(x.get("strike_price", 0)))
        if strike < low or strike > high:
            continue

        c = x.get("call_options", {}).get("market_data", {})
        p = x.get("put_options", {}).get("market_data", {})

        call_oi = float(c.get("oi", 0) or 0)
        put_oi = float(p.get("oi", 0) or 0)
        call_flow = oi_chg(c)
        put_flow = oi_chg(p)

        total_call_flow += call_flow
        total_put_flow += put_flow
        total_call_oi += call_oi
        total_put_oi += put_oi

        diff = put_flow - call_flow

        rows.append({
            "strike": strike,
            "atm": strike == atm,
            "call_oi_raw": call_oi,
            "put_oi_raw": put_oi,
            "call_flow_raw": call_flow,
            "put_flow_raw": put_flow,
            "diff_raw": diff,
            "call_oi": fmt(call_oi),
            "put_oi": fmt(put_oi),
            "call_flow": fmt(call_flow),
            "put_flow": fmt(put_flow),
            "diff": fmt(diff)
        })

    rows = sorted(rows, key=lambda x: x["strike"])

    if not rows:
        return jsonify({"error": "No OI data found"})

    strongest_put_flow = max(rows, key=lambda x: x["put_flow_raw"])
    strongest_call_flow = max(rows, key=lambda x: x["call_flow_raw"])
    strongest_bull_shift = max(rows, key=lambda x: x["diff_raw"])
    strongest_bear_shift = min(rows, key=lambda x: x["diff_raw"])

    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else 0

    bull_score = 0
    bear_score = 0
    reasons = []

    if total_put_flow > total_call_flow:
        bull_score += 35
        reasons.append("Put Flow Call કરતા વધારે")
    else:
        bear_score += 35
        reasons.append("Call Flow Put કરતા વધારે")

    if pcr > 1:
        bull_score += 20
        reasons.append("PCR 1 ઉપર")
    else:
        bear_score += 20
        reasons.append("PCR 1 નીચે")

    if strongest_bull_shift["diff_raw"] > abs(strongest_bear_shift["diff_raw"]):
        bull_score += 25
        reasons.append("Money Shift Put side તરફ")
    else:
        bear_score += 25
        reasons.append("Money Shift Call side તરફ")

    if strongest_put_flow["strike"] <= atm:
        bull_score += 10
        reasons.append("ATM નીચે Put Writing")
    if strongest_call_flow["strike"] >= atm:
        bear_score += 10
        reasons.append("ATM ઉપર Call Writing")

    total_score = bull_score + bear_score
    confidence = round((max(bull_score, bear_score) / total_score) * 100, 1) if total_score else 50

    if bull_score > bear_score and confidence >= 65:
        bias = "BULLISH"
        decision = "🟢 CALL BUY / CALL SIDE WATCH"
        color = "#d9fbe6"
    elif bear_score > bull_score and confidence >= 65:
        bias = "BEARISH"
        decision = "🔴 PUT BUY / PUT SIDE WATCH"
        color = "#ffe1e1"
    else:
        bias = "SIDEWAYS"
        decision = "🟡 NO TRADE / WAIT"
        color = "#fff3cd"

    return jsonify({
        "nifty": nifty,
        "atm": atm,
        "expiry": expiry,
        "pcr": pcr,
        "decision": decision,
        "bias": bias,
        "color": color,
        "confidence": confidence,
        "total_call_flow": fmt(total_call_flow),
        "total_put_flow": fmt(total_put_flow),
        "total_call_oi": fmt(total_call_oi),
        "total_put_oi": fmt(total_put_oi),
        "strongest_put_flow": strongest_put_flow["strike"],
        "strongest_put_flow_val": fmt(strongest_put_flow["put_flow_raw"]),
        "strongest_call_flow": strongest_call_flow["strike"],
        "strongest_call_flow_val": fmt(strongest_call_flow["call_flow_raw"]),
        "bull_shift": strongest_bull_shift["strike"],
        "bull_shift_val": fmt(strongest_bull_shift["diff_raw"]),
        "bear_shift": strongest_bear_shift["strike"],
        "bear_shift_val": fmt(strongest_bear_shift["diff_raw"]),
        "reasons": reasons[:4],
        "rows": rows,
        "time": datetime.now().strftime("%H:%M:%S")
    })

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty Money Flow OI</title>
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
.high{background:#d9fbe6!important;color:green!important;font-weight:bold}
.drop{background:#ffe1e1!important;color:red!important;font-weight:bold}
.atm{background:#fff3cd;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:10.5px;background:white}
td,th{padding:5px;border-bottom:1px solid #ddd;text-align:right}
td:first-child,th:first-child{text-align:center}
.reason{font-size:13px;margin:4px 0}
.small{text-align:center;color:#555;font-size:12px}
</style>
</head>
<body>

<div class="card">NIFTY LIVE: <span class="big" id="nifty">Loading...</span></div>
<div class="signal" id="decision">Loading...</div>

<div class="card">
<div class="grid">
<div class="box"><div class="label">ATM</div><div class="val" id="atm">-</div></div>
<div class="box"><div class="label">PCR</div><div class="val" id="pcr">-</div></div>
<div class="box"><div class="label">Bias</div><div class="val" id="bias">-</div></div>
<div class="box"><div class="label">Confidence</div><div class="val" id="confidence">-</div></div>
</div>
</div>

<div class="card">
<h3>Money Flow Summary</h3>
<div class="grid">
<div class="box"><div class="label">Total Call Flow</div><div class="val red" id="total_call_flow">-</div></div>
<div class="box"><div class="label">Total Put Flow</div><div class="val green" id="total_put_flow">-</div></div>
<div class="box"><div class="label">Strong Call Writing</div><div class="val red"><span id="strongest_call_flow">-</span><br><span id="strongest_call_flow_val"></span></div></div>
<div class="box"><div class="label">Strong Put Writing</div><div class="val green"><span id="strongest_put_flow">-</span><br><span id="strongest_put_flow_val"></span></div></div>
<div class="box"><div class="label">Bull Money Shift</div><div class="val green"><span id="bull_shift">-</span><br><span id="bull_shift_val"></span></div></div>
<div class="box"><div class="label">Bear Money Shift</div><div class="val red"><span id="bear_shift">-</span><br><span id="bear_shift_val"></span></div></div>
</div>
</div>

<div class="card">
<h3>AI Analysis Reason</h3>
<div id="reasons">Loading...</div>
</div>

<div class="card">
<h3>ATM ±10 Strike Flow</h3>
<table>
<thead>
<tr>
<th>Strike</th>
<th>Call OI</th>
<th>Call Flow</th>
<th>Put Flow</th>
<th>Put OI</th>
<th>Shift</th>
</tr>
</thead>
<tbody id="tbody"></tbody>
</table>
</div>

<p class="small">Auto refresh 2 sec | Updated: <span id="time">-</span></p>

<script>
async function loadData(){
    let r = await fetch('/api');
    let d = await r.json();

    if(d.error){
        document.getElementById('decision').innerText = d.error;
        document.getElementById('decision').style.background = '#ffe1e1';
        return;
    }

    document.getElementById('nifty').innerText = d.nifty;
    document.getElementById('decision').innerText = d.decision;
    document.getElementById('decision').style.background = d.color;
    document.getElementById('atm').innerText = d.atm;
    document.getElementById('pcr').innerText = d.pcr;
    document.getElementById('bias').innerText = d.bias;
    document.getElementById('confidence').innerText = d.confidence + "%";

    document.getElementById('total_call_flow').innerText = d.total_call_flow;
    document.getElementById('total_put_flow').innerText = d.total_put_flow;

    document.getElementById('strongest_call_flow').innerText = d.strongest_call_flow;
    document.getElementById('strongest_call_flow_val').innerText = d.strongest_call_flow_val;
    document.getElementById('strongest_put_flow').innerText = d.strongest_put_flow;
    document.getElementById('strongest_put_flow_val').innerText = d.strongest_put_flow_val;

    document.getElementById('bull_shift').innerText = d.bull_shift;
    document.getElementById('bull_shift_val').innerText = d.bull_shift_val;
    document.getElementById('bear_shift').innerText = d.bear_shift;
    document.getElementById('bear_shift_val').innerText = d.bear_shift_val;

    document.getElementById('time').innerText = d.time;

    let reasons = "";
    d.reasons.forEach(x=>{
        reasons += `<div class="reason">• ${x}</div>`;
    });
    document.getElementById('reasons').innerHTML = reasons;

    let html = "";
    d.rows.forEach(x=>{
        html += `
        <tr class="${x.atm ? 'atm' : ''}">
            <td>${x.strike}</td>
            <td class="red">${x.call_oi}</td>
            <td class="${x.call_flow_raw < 0 ? 'green' : 'red'}">${x.call_flow}</td>
            <td class="${x.put_flow_raw > 0 ? 'green' : 'red'}">${x.put_flow}</td>
            <td class="green">${x.put_oi}</td>
            <td class="${x.diff_raw >= 0 ? 'green' : 'red'}">${x.diff}</td>
        </tr>`;
    });

    document.getElementById('tbody').innerHTML = html;
}

loadData();
setInterval(loadData, 2000);
</script>

</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)
