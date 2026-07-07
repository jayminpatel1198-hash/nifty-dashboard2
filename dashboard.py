from flask import Flask, render_template_string, jsonify
import requests, os
from datetime import datetime

app = Flask(__name__)

TOKEN = os.environ.get("UPSTOX_TOKEN")
UNDERLYING = "NSE_INDEX|Nifty 50"
STRIKE_STEP = 50
AROUND_STRIKES = 10

def auth_headers():
    return {"Accept": "application/json", "Authorization": "Bearer " + TOKEN}

def fmt(n):
    try:
        n = float(n)
        sign = "-" if n < 0 else ""
        n = abs(n)
        if n >= 10000000: return sign + str(round(n / 10000000, 2)) + "Cr"
        if n >= 100000: return sign + str(round(n / 100000, 2)) + "L"
        if n >= 1000: return sign + str(round(n / 1000, 1)) + "K"
        return sign + str(int(n))
    except:
        return "-"

def oi_change(md):
    for k in ["oi_day_change", "oi_change", "change_oi", "oi_change_value"]:
        v = md.get(k)
        if v not in [None, ""]:
            return float(v or 0)
    oi = float(md.get("oi", 0) or 0)
    prev = float(md.get("previous_oi", 0) or md.get("prev_oi", 0) or 0)
    return oi - prev if prev else 0

def get_expiry():
    env_expiry = os.environ.get("EXPIRY_DATE")
    if env_expiry:
        return env_expiry

    r = requests.get(
        "https://api.upstox.com/v2/option/contract",
        headers=auth_headers(),
        params={"instrument_key": UNDERLYING},
        timeout=10
    )
    js = r.json()
    expiries = sorted(list(set([x.get("expiry") for x in js.get("data", []) if x.get("expiry")])))
    if not expiries:
        raise Exception("Expiry not found. Render Environment ma EXPIRY_DATE add karo.")
    return expiries[0]

@app.route("/api")
def api():
    if not TOKEN:
        return jsonify({"error": "UPSTOX_TOKEN missing"})

    try:
        ltp = requests.get(
            "https://api.upstox.com/v2/market-quote/ltp",
            headers=auth_headers(),
            params={"instrument_key": UNDERLYING},
            timeout=10
        ).json()
        nifty = float(ltp["data"]["NSE_INDEX:Nifty 50"]["last_price"])
    except Exception as e:
        return jsonify({"error": "Nifty price error: " + str(e)})

    try:
        expiry = get_expiry()
        oc = requests.get(
            "https://api.upstox.com/v2/option/chain",
            headers=auth_headers(),
            params={"instrument_key": UNDERLYING, "expiry_date": expiry},
            timeout=15
        ).json()

        if oc.get("status") != "success":
            return jsonify({"error": str(oc)})

        data = oc.get("data", [])
    except Exception as e:
        return jsonify({"error": "Option chain error: " + str(e)})

    atm = round(nifty / STRIKE_STEP) * STRIKE_STEP
    low = atm - AROUND_STRIKES * STRIKE_STEP
    high = atm + AROUND_STRIKES * STRIKE_STEP

    rows = []
    total_call_oi = total_put_oi = 0
    total_call_chg = total_put_chg = 0

    for x in data:
        strike = int(float(x.get("strike_price", 0)))
        if strike < low or strike > high:
            continue

        call_md = x.get("call_options", {}).get("market_data", {})
        put_md = x.get("put_options", {}).get("market_data", {})

        call_oi = float(call_md.get("oi", 0) or 0)
        put_oi = float(put_md.get("oi", 0) or 0)
        call_chg = oi_change(call_md)
        put_chg = oi_change(put_md)

        total_call_oi += call_oi
        total_put_oi += put_oi
        total_call_chg += call_chg
        total_put_chg += put_chg

        rows.append({
            "strike": strike,
            "atm": strike == atm,
            "call_oi": call_oi,
            "put_oi": put_oi,
            "call_chg": call_chg,
            "put_chg": put_chg,
            "call_oi_f": fmt(call_oi),
            "put_oi_f": fmt(put_oi),
            "call_chg_f": fmt(call_chg),
            "put_chg_f": fmt(put_chg)
        })

    rows = sorted(rows, key=lambda x: x["strike"])
    if not rows:
        return jsonify({"error": "No OI data found"})

    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else 0
    pcr_chg = round(total_put_chg / total_call_chg, 2) if total_call_chg else 0

    high_call_oi = max(rows, key=lambda x: x["call_oi"])
    high_put_oi = max(rows, key=lambda x: x["put_oi"])
    high_call_chg = max(rows, key=lambda x: x["call_chg"])
    high_put_chg = max(rows, key=lambda x: x["put_chg"])
    call_unwind = min(rows, key=lambda x: x["call_chg"])
    put_unwind = min(rows, key=lambda x: x["put_chg"])

    bullish_points = 0
    bearish_points = 0

    if total_put_chg > total_call_chg: bullish_points += 1
    if total_call_chg > total_put_chg: bearish_points += 1
    if pcr > 1: bullish_points += 1
    if pcr < 1: bearish_points += 1
    if call_unwind["call_chg"] < 0: bullish_points += 1
    if put_unwind["put_chg"] < 0: bearish_points += 1

    if bullish_points > bearish_points:
        decision = "🟢 CALL SIDE WATCH - OI BULLISH"
        color = "#d9fbe6"
    elif bearish_points > bullish_points:
        decision = "🔴 PUT SIDE WATCH - OI BEARISH"
        color = "#ffe1e1"
    else:
        decision = "🟡 MIXED / WAIT"
        color = "#fff3cd"

    return jsonify({
        "nifty": nifty,
        "atm": atm,
        "expiry": expiry,
        "decision": decision,
        "color": color,
        "pcr": pcr,
        "pcr_chg": pcr_chg,
        "total_call_oi": fmt(total_call_oi),
        "total_put_oi": fmt(total_put_oi),
        "total_call_chg": fmt(total_call_chg),
        "total_put_chg": fmt(total_put_chg),
        "resistance": high_call_oi["strike"],
        "support": high_put_oi["strike"],
        "call_writing": high_call_chg["strike"],
        "put_writing": high_put_chg["strike"],
        "call_unwind": call_unwind["strike"],
        "put_unwind": put_unwind["strike"],
        "call_writing_val": fmt(high_call_chg["call_chg"]),
        "put_writing_val": fmt(high_put_chg["put_chg"]),
        "call_unwind_val": fmt(call_unwind["call_chg"]),
        "put_unwind_val": fmt(put_unwind["put_chg"]),
        "rows": rows,
        "time": datetime.now().strftime("%H:%M:%S")
    })

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty OI Dashboard</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0;padding:8px}
.card{background:white;padding:12px;margin:7px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.big{font-size:24px;font-weight:bold}
.signal{padding:15px;border-radius:14px;text-align:center;font-size:21px;font-weight:bold;margin:7px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.box{background:#f8f9fa;border-radius:12px;padding:9px;text-align:center}
.label{font-size:12px;color:#555}.val{font-size:18px;font-weight:bold}
.green{color:green;font-weight:bold}.red{color:red;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:12px;background:white}
td,th{padding:6px;border-bottom:1px solid #ddd;text-align:right}
td:first-child,th:first-child{text-align:center}
.atm{background:#fff3cd;font-weight:bold}
.small{text-align:center;color:#555;font-size:12px}
</style>
</head>
<body>

<div class="card">NIFTY LIVE: <span class="big" id="nifty">Loading...</span></div>
<div class="signal" id="decision">Loading OI...</div>

<div class="card">
<div class="grid">
<div class="box"><div class="label">ATM Strike</div><div class="val" id="atm">-</div></div>
<div class="box"><div class="label">Expiry</div><div class="val" id="expiry">-</div></div>
<div class="box"><div class="label">PCR OI</div><div class="val" id="pcr">-</div></div>
<div class="box"><div class="label">PCR Change</div><div class="val" id="pcrchg">-</div></div>

<div class="box"><div class="label">Resistance CE</div><div class="val red" id="resistance">-</div></div>
<div class="box"><div class="label">Support PE</div><div class="val green" id="support">-</div></div>

<div class="box"><div class="label">Call Writing</div><div class="val red"><span id="callwriting">-</span><br><span id="callwritingv"></span></div></div>
<div class="box"><div class="label">Put Writing</div><div class="val green"><span id="putwriting">-</span><br><span id="putwritingv"></span></div></div>

<div class="box"><div class="label">Call Unwinding</div><div class="val green"><span id="callunwind">-</span><br><span id="callunwindv"></span></div></div>
<div class="box"><div class="label">Put Unwinding</div><div class="val red"><span id="putunwind">-</span><br><span id="putunwindv"></span></div></div>

<div class="box"><div class="label">Total Call OI</div><div class="val red" id="tcoi">-</div></div>
<div class="box"><div class="label">Total Put OI</div><div class="val green" id="tpoi">-</div></div>
<div class="box"><div class="label">Total Call Chg OI</div><div class="val red" id="tcchg">-</div></div>
<div class="box"><div class="label">Total Put Chg OI</div><div class="val green" id="tpchg">-</div></div>
</div>
</div>

<div class="card">
<h3>ATM ± 10 Strikes Live OI</h3>
<table>
<thead>
<tr><th>Strike</th><th>Call OI</th><th>Call Chg</th><th>Put Chg</th><th>Put OI</th></tr>
</thead>
<tbody id="tbody"></tbody>
</table>
</div>

<p class="small">Auto refresh 2 sec | Updated: <span id="time">-</span></p>

<script>
async function loadData(){
    try{
        let r = await fetch("/api");
        let d = await r.json();

        if(d.error){
            document.getElementById("decision").innerText = d.error;
            document.getElementById("decision").style.background = "#ffe1e1";
            return;
        }

        document.getElementById("nifty").innerText = d.nifty;
        document.getElementById("decision").innerText = d.decision;
        document.getElementById("decision").style.background = d.color;

        document.getElementById("atm").innerText = d.atm;
        document.getElementById("expiry").innerText = d.expiry;
        document.getElementById("pcr").innerText = d.pcr;
        document.getElementById("pcrchg").innerText = d.pcr_chg;

        document.getElementById("resistance").innerText = d.resistance;
        document.getElementById("support").innerText = d.support;
        document.getElementById("callwriting").innerText = d.call_writing;
        document.getElementById("putwriting").innerText = d.put_writing;
        document.getElementById("callunwind").innerText = d.call_unwind;
        document.getElementById("putunwind").innerText = d.put_unwind;

        document.getElementById("callwritingv").innerText = d.call_writing_val;
        document.getElementById("putwritingv").innerText = d.put_writing_val;
        document.getElementById("callunwindv").innerText = d.call_unwind_val;
        document.getElementById("putunwindv").innerText = d.put_unwind_val;

        document.getElementById("tcoi").innerText = d.total_call_oi;
        document.getElementById("tpoi").innerText = d.total_put_oi;
        document.getElementById("tcchg").innerText = d.total_call_chg;
        document.getElementById("tpchg").innerText = d.total_put_chg;
        document.getElementById("time").innerText = d.time;

        let html = "";
        d.rows.forEach(x=>{
            let row = x.atm ? "atm" : "";
            let cc = x.call_chg < 0 ? "green" : "red";
            let pc = x.put_chg > 0 ? "green" : "red";

            html += `<tr class="${row}">
                <td>${x.strike}</td>
                <td class="red">${x.call_oi_f}</td>
                <td class="${cc}">${x.call_chg_f}</td>
                <td class="${pc}">${x.put_chg_f}</td>
                <td class="green">${x.put_oi_f}</td>
            </tr>`;
        });

        document.getElementById("tbody").innerHTML = html;

    }catch(e){
        document.getElementById("decision").innerText = "Data load failed";
        document.getElementById("decision").style.background = "#ffe1e1";
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
