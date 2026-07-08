from flask import Flask, render_template_string, jsonify
import requests, os
from datetime import datetime

app = Flask(__name__)

TOKEN = os.environ.get("UPSTOX_TOKEN")
UNDERLYING = "NSE_INDEX|Nifty 50"
STRIKE_STEP = 50
AROUND_STRIKES = 10

def headers():
    return {"Accept": "application/json", "Authorization": "Bearer " + TOKEN}

def fmt(n):
    try:
        n = float(n)
        sign = "+" if n > 0 else "-" if n < 0 else ""
        n = abs(n)
        if n >= 10000000: return sign + str(round(n/10000000, 2)) + "Cr"
        if n >= 100000: return sign + str(round(n/100000, 2)) + "L"
        if n >= 1000: return sign + str(round(n/1000, 1)) + "K"
        return sign + str(int(n))
    except:
        return "-"

def oi_chg(md):
    for k in ["oi_day_change","oi_change","change_oi","oi_change_value","change_in_oi"]:
        v = md.get(k)
        if v not in [None, ""]:
            return float(v or 0)
    oi = float(md.get("oi", 0) or 0)
    prev = float(md.get("previous_oi", 0) or md.get("prev_oi", 0) or md.get("close_oi", 0) or 0)
    return oi - prev if prev else 0

def get_expiry():
    e = os.environ.get("EXPIRY_DATE")
    if e:
        return e
    r = requests.get(
        "https://api.upstox.com/v2/option/contract",
        headers=headers(),
        params={"instrument_key": UNDERLYING},
        timeout=10
    ).json()
    expiries = sorted(list(set([x.get("expiry") for x in r.get("data", []) if x.get("expiry")])))
    if not expiries:
        raise Exception("EXPIRY_DATE Render Environment માં add કરો")
    return expiries[0]

@app.route("/api")
def api():
    if not TOKEN:
        return jsonify({"error": "UPSTOX_TOKEN missing"})

    try:
        ltp = requests.get(
            "https://api.upstox.com/v2/market-quote/ltp",
            headers=headers(),
            params={"instrument_key": UNDERLYING},
            timeout=10
        ).json()
        nifty = float(ltp["data"]["NSE_INDEX:Nifty 50"]["last_price"])

        expiry = get_expiry()

        oc = requests.get(
            "https://api.upstox.com/v2/option/chain",
            headers=headers(),
            params={"instrument_key": UNDERLYING, "expiry_date": expiry},
            timeout=15
        ).json()

        if oc.get("status") != "success":
            return jsonify({"error": str(oc)})

        data = oc.get("data", [])

    except Exception as e:
        return jsonify({"error": str(e)})

    atm = round(nifty / STRIKE_STEP) * STRIKE_STEP
    low = atm - AROUND_STRIKES * STRIKE_STEP
    high = atm + AROUND_STRIKES * STRIKE_STEP

    rows = []
    total_call_oi = total_put_oi = 0
    total_call_chg = total_put_chg = 0
    total_call_total = total_put_total = 0

    for x in data:
        strike = int(float(x.get("strike_price", 0)))
        if strike < low or strike > high:
            continue

        c = x.get("call_options", {}).get("market_data", {})
        p = x.get("put_options", {}).get("market_data", {})

        call_oi = float(c.get("oi", 0) or 0)
        put_oi = float(p.get("oi", 0) or 0)

        call_chg = oi_chg(c)
        put_chg = oi_chg(p)

        call_total = call_oi + call_chg
        put_total = put_oi + put_chg
        diff = put_total - call_total

        total_call_oi += call_oi
        total_put_oi += put_oi
        total_call_chg += call_chg
        total_put_chg += put_chg
        total_call_total += call_total
        total_put_total += put_total

        rows.append({
            "strike": strike,
            "atm": strike == atm,

            "call_oi_raw": call_oi,
            "call_chg_raw": call_chg,
            "call_total_raw": call_total,

            "put_oi_raw": put_oi,
            "put_chg_raw": put_chg,
            "put_total_raw": put_total,

            "diff_raw": diff,

            "call_oi": fmt(call_oi),
            "call_chg": fmt(call_chg),
            "call_total": fmt(call_total),

            "put_oi": fmt(put_oi),
            "put_chg": fmt(put_chg),
            "put_total": fmt(put_total),

            "diff": fmt(diff)
        })

    rows = sorted(rows, key=lambda x: x["strike"])

    if not rows:
        return jsonify({"error": "No option chain data found"})

    max_call_oi = max(r["call_oi_raw"] for r in rows)
    max_call_chg = max(r["call_chg_raw"] for r in rows)
    max_call_total = max(r["call_total_raw"] for r in rows)

    max_put_oi = max(r["put_oi_raw"] for r in rows)
    max_put_chg = max(r["put_chg_raw"] for r in rows)
    max_put_total = max(r["put_total_raw"] for r in rows)

    strongest_bull = max(rows, key=lambda x: x["diff_raw"])
    strongest_bear = min(rows, key=lambda x: x["diff_raw"])

    for r in rows:
        r["max_call_oi"] = r["call_oi_raw"] == max_call_oi and max_call_oi > 0
        r["max_call_chg"] = r["call_chg_raw"] == max_call_chg and max_call_chg > 0
        r["max_call_total"] = r["call_total_raw"] == max_call_total and max_call_total > 0

        r["max_put_oi"] = r["put_oi_raw"] == max_put_oi and max_put_oi > 0
        r["max_put_chg"] = r["put_chg_raw"] == max_put_chg and max_put_chg > 0
        r["max_put_total"] = r["put_total_raw"] == max_put_total and max_put_total > 0

    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else 0
    final_diff = total_put_total - total_call_total

    bull_score = 0
    bear_score = 0
    reasons = []

    if total_put_chg > total_call_chg:
        bull_score += 30
        reasons.append("Put change વધારે છે એટલે support વધી શકે")
    else:
        bear_score += 30
        reasons.append("Call change વધારે છે એટલે resistance વધી શકે")

    if final_diff > 0:
        bull_score += 30
        reasons.append("Put total Call total કરતા વધારે છે")
    else:
        bear_score += 30
        reasons.append("Call total Put total કરતા વધારે છે")

    if pcr > 1:
        bull_score += 20
        reasons.append("PCR 1 ઉપર છે")
    else:
        bear_score += 20
        reasons.append("PCR 1 નીચે છે")

    if strongest_bull["diff_raw"] > abs(strongest_bear["diff_raw"]):
        bull_score += 20
        reasons.append("Bullish strike pressure વધારે છે")
    else:
        bear_score += 20
        reasons.append("Bearish strike pressure વધારે છે")

    total_score = bull_score + bear_score
    market_score = round((bull_score / total_score) * 100, 1) if total_score else 50
    confidence = round(abs(market_score - 50) * 2, 1)

    if market_score >= 70:
        decision = "🟢 CALL BUY / Market વધવાની શક્યતા"
        color = "#d9fbe6"
    elif market_score >= 56:
        decision = "🟢 CALL SIDE WATCH"
        color = "#fff3cd"
    elif market_score <= 30:
        decision = "🔴 PUT BUY / Market ઘટવાની શક્યતા"
        color = "#ffe1e1"
    elif market_score <= 44:
        decision = "🔴 PUT SIDE WATCH"
        color = "#fff3cd"
    else:
        decision = "🟡 WAIT / Sideways"
        color = "#fff3cd"

    return jsonify({
        "nifty": nifty,
        "atm": atm,
        "expiry": expiry,
        "pcr": pcr,

        "decision": decision,
        "color": color,
        "market_score": market_score,
        "confidence": confidence,

        "total_call_oi": fmt(total_call_oi),
        "total_call_chg": fmt(total_call_chg),
        "total_call_total": fmt(total_call_total),

        "total_put_oi": fmt(total_put_oi),
        "total_put_chg": fmt(total_put_chg),
        "total_put_total": fmt(total_put_total),

        "final_diff": fmt(final_diff),

        "strongest_bull_strike": strongest_bull["strike"],
        "strongest_bull_val": fmt(strongest_bull["diff_raw"]),
        "strongest_bear_strike": strongest_bear["strike"],
        "strongest_bear_val": fmt(strongest_bear["diff_raw"]),

        "reasons": reasons[:4],
        "rows": rows,
        "time": datetime.now().strftime("%H:%M:%S")
    })

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty Ultra OI Dashboard</title>
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
.atm{background:#fff3cd;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:10px;background:white}
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
<div class="box"><div class="label">ATM Strike</div><div class="val" id="atm">-</div></div>
<div class="box"><div class="label">PCR</div><div class="val" id="pcr">-</div></div>
<div class="box"><div class="label">Market Score</div><div class="val" id="market_score">-</div></div>
<div class="box"><div class="label">Confidence</div><div class="val" id="confidence">-</div></div>
</div>
</div>

<div class="card">
<h3>Call / Put Total Summary</h3>
<div class="grid">
<div class="box"><div class="label">Call OI</div><div class="val red" id="total_call_oi">-</div></div>
<div class="box"><div class="label">Put OI</div><div class="val green" id="total_put_oi">-</div></div>
<div class="box"><div class="label">Call Change</div><div class="val red" id="total_call_chg">-</div></div>
<div class="box"><div class="label">Put Change</div><div class="val green" id="total_put_chg">-</div></div>
<div class="box"><div class="label">Call Total</div><div class="val red" id="total_call_total">-</div></div>
<div class="box"><div class="label">Put Total</div><div class="val green" id="total_put_total">-</div></div>
<div class="box"><div class="label">Put - Call Diff</div><div class="val blue" id="final_diff">-</div></div>
<div class="box"><div class="label">Updated</div><div class="val" id="time">-</div></div>
</div>
</div>

<div class="card">
<h3>Money Shift</h3>
<div class="grid">
<div class="box"><div class="label">Bullish Strike</div><div class="val green"><span id="strongest_bull_strike">-</span><br><span id="strongest_bull_val"></span></div></div>
<div class="box"><div class="label">Bearish Strike</div><div class="val red"><span id="strongest_bear_strike">-</span><br><span id="strongest_bear_val"></span></div></div>
</div>
</div>

<div class="card">
<h3>Gujarati Analysis</h3>
<div id="reasons">Loading...</div>
</div>

<div class="card">
<h3>ATM ± 10 Strike Ultra Table</h3>
<table>
<thead>
<tr>
<th>Strike</th>
<th>Call OI</th>
<th>Call Chg</th>
<th>Call Total</th>
<th>Put Total</th>
<th>Put Chg</th>
<th>Put OI</th>
<th>Diff</th>
</tr>
</thead>
<tbody id="tbody"></tbody>
</table>
</div>

<p class="small">Auto refresh 2 sec | Expiry: <span id="expiry">-</span></p>

<script>
async function loadData(){
    try{
        let r = await fetch('/api');
        let d = await r.json();

        if(d.error){
            document.getElementById('decision').innerText = d.error;
            document.getElementById('decision').style.background = '#ffe1e1';
            return;
        }

        document.getElementById('nifty').innerText = d.nifty;
        document.getElementById('atm').innerText = d.atm;
        document.getElementById('expiry').innerText = d.expiry;
        document.getElementById('pcr').innerText = d.pcr;
        document.getElementById('decision').innerText = d.decision;
        document.getElementById('decision').style.background = d.color;
        document.getElementById('market_score').innerText = d.market_score + "/100";
        document.getElementById('confidence').innerText = d.confidence + "%";

        document.getElementById('total_call_oi').innerText = d.total_call_oi;
        document.getElementById('total_call_chg').innerText = d.total_call_chg;
        document.getElementById('total_call_total').innerText = d.total_call_total;

        document.getElementById('total_put_oi').innerText = d.total_put_oi;
        document.getElementById('total_put_chg').innerText = d.total_put_chg;
        document.getElementById('total_put_total').innerText = d.total_put_total;

        document.getElementById('final_diff').innerText = d.final_diff;
        document.getElementById('time').innerText = d.time;

        document.getElementById('strongest_bull_strike').innerText = d.strongest_bull_strike;
        document.getElementById('strongest_bull_val').innerText = d.strongest_bull_val;
        document.getElementById('strongest_bear_strike').innerText = d.strongest_bear_strike;
        document.getElementById('strongest_bear_val').innerText = d.strongest_bear_val;

        let reasonHtml = "";
        d.reasons.forEach(x=>{
            reasonHtml += `<div class="reason">• ${x}</div>`;
        });
        document.getElementById('reasons').innerHTML = reasonHtml;

        let html = "";
        d.rows.forEach(x=>{
            html += `
            <tr class="${x.atm ? 'atm' : ''}">
                <td>${x.strike}</td>
                <td class="${x.max_call_oi ? 'high' : 'red'}">${x.call_oi}</td>
                <td class="${x.max_call_chg ? 'high' : (x.call_chg_raw < 0 ? 'green' : 'red')}">${x.call_chg}</td>
                <td class="${x.max_call_total ? 'high' : 'red'}">${x.call_total}</td>
                <td class="${x.max_put_total ? 'high' : 'green'}">${x.put_total}</td>
                <td class="${x.max_put_chg ? 'high' : (x.put_chg_raw > 0 ? 'green' : 'red')}">${x.put_chg}</td>
                <td class="${x.max_put_oi ? 'high' : 'green'}">${x.put_oi}</td>
                <td class="${x.diff_raw >= 0 ? 'green' : 'red'}">${x.diff}</td>
            </tr>`;
        });

        document.getElementById('tbody').innerHTML = html;

    }catch(e){
        document.getElementById('decision').innerText = "Data load failed";
        document.getElementById('decision').style.background = '#ffe1e1';
    }
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
    
