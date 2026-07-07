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
        sign = "-" if n < 0 else ""
        n = abs(n)
        if n >= 10000000: return sign + str(round(n/10000000,2)) + "Cr"
        if n >= 100000: return sign + str(round(n/100000,2)) + "L"
        if n >= 1000: return sign + str(round(n/1000,1)) + "K"
        return sign + str(int(n))
    except:
        return "-"

def get_expiry():
    env_exp = os.environ.get("EXPIRY_DATE")
    if env_exp:
        return env_exp

    r = requests.get(
        "https://api.upstox.com/v2/option/contract",
        headers=headers(),
        params={"instrument_key": UNDERLYING},
        timeout=10
    )
    js = r.json()
    expiries = sorted(list(set([x.get("expiry") for x in js.get("data", []) if x.get("expiry")])))
    if not expiries:
        raise Exception("Expiry not found. Render Environment ma EXPIRY_DATE add karo. Example: 2026-06-25")
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
    except Exception as e:
        return jsonify({"error": "Nifty LTP Error: " + str(e)})

    try:
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
        return jsonify({"error": "Option Chain Error: " + str(e)})

    atm = round(nifty / STRIKE_STEP) * STRIKE_STEP
    low = atm - (AROUND_STRIKES * STRIKE_STEP)
    high = atm + (AROUND_STRIKES * STRIKE_STEP)

    rows = []
    total_call_oi = total_put_oi = 0
    total_call_chg = total_put_chg = 0

    for x in data:
        strike = int(float(x.get("strike_price", 0)))
        if strike < low or strike > high:
            continue

        call_md = x.get("call_options", {}).get("market_data", {})
        put_md = x.get("put_options", {}).get("market_data", {})

        call_oi = call_md.get("oi", 0) or 0
        put_oi = put_md.get("oi", 0) or 0

        call_chg = (
            call_md.get("oi_day_change", 0)
            or call_md.get("oi_change", 0)
            or call_md.get("change_oi", 0)
            or 0
        )
        put_chg = (
            put_md.get("oi_day_change", 0)
            or put_md.get("oi_change", 0)
            or put_md.get("change_oi", 0)
            or 0
        )

        total_call_oi += call_oi
        total_put_oi += put_oi
        total_call_chg += call_chg
        total_put_chg += put_chg

        rows.append({
            "strike": strike,
            "is_atm": strike == atm,
            "call_oi": fmt(call_oi),
            "call_chg": fmt(call_chg),
            "put_chg": fmt(put_chg),
            "put_oi": fmt(put_oi),
            "raw_call_chg": call_chg,
            "raw_put_chg": put_chg
        })

    rows = sorted(rows, key=lambda x: x["strike"])

    if total_put_chg > total_call_chg:
        decision = "🟢 BULLISH OI - PUT WRITING STRONG"
        color = "#d9fbe6"
    elif total_call_chg > total_put_chg:
        decision = "🔴 BEARISH OI - CALL WRITING STRONG"
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
        "totals": {
            "call_oi": fmt(total_call_oi),
            "put_oi": fmt(total_put_oi),
            "call_chg": fmt(total_call_chg),
            "put_chg": fmt(total_put_chg)
        },
        "rows": rows,
        "time": datetime.now().strftime("%H:%M:%S")
    })

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty Live OI</title>
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
<tr>
<th>Strike</th>
<th>Call OI</th>
<th>Call Chg</th>
<th>Put Chg</th>
<th>Put OI</th>
</tr>
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
        document.getElementById("atm").innerText = d.atm;
        document.getElementById("expiry").innerText = d.expiry;

        document.getElementById("decision").innerText = d.decision;
        document.getElementById("decision").style.background = d.color;

        document.getElementById("tcoi").innerText = d.totals.call_oi;
        document.getElementById("tpoi").innerText = d.totals.put_oi;
        document.getElementById("tcchg").innerText = d.totals.call_chg;
        document.getElementById("tpchg").innerText = d.totals.put_chg;

        let html = "";
        d.rows.forEach(x=>{
            let cls = x.is_atm ? "atm" : "";
            let cc = x.raw_call_chg < 0 ? "green" : "red";
            let pc = x.raw_put_chg > 0 ? "green" : "red";

            html += `<tr class="${cls}">
                <td>${x.strike}</td>
                <td class="red">${x.call_oi}</td>
                <td class="${cc}">${x.call_chg}</td>
                <td class="${pc}">${x.put_chg}</td>
                <td class="green">${x.put_oi}</td>
            </tr>`;
        });

        document.getElementById("tbody").innerHTML = html;
        document.getElementById("time").innerText = d.time;

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
