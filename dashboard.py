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
        if n >= 10000000: return sign + str(round(n / 10000000, 2)) + "Cr"
        if n >= 100000: return sign + str(round(n / 100000, 2)) + "L"
        if n >= 1000: return sign + str(round(n / 1000, 1)) + "K"
        return sign + str(int(n))
    except:
        return "-"

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
        raise Exception("Render Environment માં EXPIRY_DATE add કરો")
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

        data = oc.get("data", [])

    except Exception as e:
        return jsonify({"error": str(e)})

    atm = round(nifty / STRIKE_STEP) * STRIKE_STEP
    low = atm - AROUND_STRIKES * STRIKE_STEP
    high = atm + AROUND_STRIKES * STRIKE_STEP

    rows = []
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

        total_call_oi += call_oi
        total_put_oi += put_oi

        rows.append({
            "strike": strike,
            "atm": strike == atm,
            "call_oi_raw": call_oi,
            "put_oi_raw": put_oi,
            "call_oi": fmt(call_oi),
            "put_oi": fmt(put_oi)
        })

    rows = sorted(rows, key=lambda x: x["strike"])

    return jsonify({
        "nifty": nifty,
        "atm": atm,
        "expiry": expiry,
        "total_call_oi_raw": total_call_oi,
        "total_put_oi_raw": total_put_oi,
        "total_call_oi": fmt(total_call_oi),
        "total_put_oi": fmt(total_put_oi),
        "rows": rows,
        "time": datetime.now().strftime("%H:%M:%S")
    })

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty Live OI Simple</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0;padding:8px}
.card{background:white;padding:12px;margin:7px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.big{font-size:24px;font-weight:bold}
.signal{padding:15px;border-radius:14px;text-align:center;font-size:22px;font-weight:bold;margin:7px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.box{background:#f8f9fa;border-radius:12px;padding:9px;text-align:center}
.label{font-size:12px;color:#555}
.val{font-size:18px;font-weight:bold}
.green{color:green;font-weight:bold}
.red{color:red;font-weight:bold}
.blue{color:#064fcb;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:11px;background:white}
td,th{padding:5px;border-bottom:1px solid #ddd;text-align:right}
td:first-child,th:first-child{text-align:center}
.atm{background:#fff3cd;font-weight:bold}
.up{background:#d9fbe6;color:green;font-weight:bold}
.down{background:#ffe1e1;color:red;font-weight:bold}
.small{text-align:center;color:#555;font-size:12px}
</style>
</head>
<body>

<div class="card">NIFTY LIVE: <span class="big" id="nifty">Loading...</span></div>
<div class="signal" id="decision">Loading...</div>

<div class="card">
<div class="grid">
<div class="box"><div class="label">ATM Strike</div><div class="val" id="atm">-</div></div>
<div class="box"><div class="label">Updated</div><div class="val" id="time">-</div></div>

<div class="box"><div class="label">Call OI Total</div><div class="val red" id="call_total">-</div></div>
<div class="box"><div class="label">Put OI Total</div><div class="val green" id="put_total">-</div></div>

<div class="box"><div class="label">Call Live Change</div><div class="val red" id="call_live">-</div></div>
<div class="box"><div class="label">Put Live Change</div><div class="val green" id="put_live">-</div></div>

<div class="box"><div class="label">Put - Call Live Diff</div><div class="val blue" id="live_diff">-</div></div>
<div class="box"><div class="label">Expiry</div><div class="val" id="expiry">-</div></div>
</div>
</div>

<div class="card">
<h3>Strike Wise Live Change</h3>
<table>
<thead>
<tr>
<th>Strike</th>
<th>Call OI</th>
<th>Call Live</th>
<th>Put Live</th>
<th>Put OI</th>
<th>Diff</th>
</tr>
</thead>
<tbody id="tbody"></tbody>
</table>
</div>

<p class="small">Auto refresh 2 sec | Live Change = છેલ્લા refresh પછી OI બદલાવ</p>

<script>
let previous = {};
let firstLoad = true;

function fmt(n){
    n = Number(n || 0);
    let sign = n > 0 ? "+" : n < 0 ? "-" : "";
    n = Math.abs(n);
    if(n >= 10000000) return sign + (n/10000000).toFixed(2) + "Cr";
    if(n >= 100000) return sign + (n/100000).toFixed(2) + "L";
    if(n >= 1000) return sign + (n/1000).toFixed(1) + "K";
    return sign + Math.round(n);
}

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
        document.getElementById("time").innerText = d.time;
        document.getElementById("call_total").innerText = d.total_call_oi;
        document.getElementById("put_total").innerText = d.total_put_oi;

        let callLiveTotal = 0;
        let putLiveTotal = 0;
        let html = "";

        d.rows.forEach(x => {
            let old = previous[x.strike] || {
                call: x.call_oi_raw,
                put: x.put_oi_raw
            };

            let callLive = firstLoad ? 0 : x.call_oi_raw - old.call;
            let putLive = firstLoad ? 0 : x.put_oi_raw - old.put;
            let diff = putLive - callLive;

            callLiveTotal += callLive;
            putLiveTotal += putLive;

            let callClass = callLive > 0 ? "down" : callLive < 0 ? "up" : "red";
            let putClass = putLive > 0 ? "up" : putLive < 0 ? "down" : "green";
            let diffClass = diff > 0 ? "green" : diff < 0 ? "red" : "blue";

            html += `
            <tr class="${x.atm ? 'atm' : ''}">
                <td>${x.strike}</td>
                <td class="red">${x.call_oi}</td>
                <td class="${callClass}">${fmt(callLive)}</td>
                <td class="${putClass}">${fmt(putLive)}</td>
                <td class="green">${x.put_oi}</td>
                <td class="${diffClass}">${fmt(diff)}</td>
            </tr>`;

            previous[x.strike] = {
                call: x.call_oi_raw,
                put: x.put_oi_raw
            };
        });

        firstLoad = false;

        let liveDiff = putLiveTotal - callLiveTotal;

        document.getElementById("call_live").innerText = fmt(callLiveTotal);
        document.getElementById("put_live").innerText = fmt(putLiveTotal);
        document.getElementById("live_diff").innerText = fmt(liveDiff);

        if(liveDiff > 0){
            document.getElementById("decision").innerText = "🟢 Market વધવાની શક્યતા - CALL SIDE";
            document.getElementById("decision").style.background = "#d9fbe6";
        }else if(liveDiff < 0){
            document.getElementById("decision").innerText = "🔴 Market ઘટવાની શક્યતા - PUT SIDE";
            document.getElementById("decision").style.background = "#ffe1e1";
        }else{
            document.getElementById("decision").innerText = "🟡 Clear signal નથી - WAIT";
            document.getElementById("decision").style.background = "#fff3cd";
        }

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
