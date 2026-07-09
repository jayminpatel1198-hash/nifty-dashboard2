from flask import Flask, render_template_string, jsonify
import requests, os
from datetime import datetime

app = Flask(__name__)
TOKEN = os.environ.get("UPSTOX_TOKEN")

UNDERLYING = "NSE_INDEX|Nifty 50"
STRIKE_STEP = 50
AROUND_STRIKES = 5

def headers():
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

def oi_change(md):
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
    total_call_oi = 0
    total_put_oi = 0
    total_call_chg = 0
    total_put_chg = 0

    for x in data:
        strike = int(float(x.get("strike_price", 0)))
        if strike < low or strike > high:
            continue

        c = x.get("call_options", {}).get("market_data", {})
        p = x.get("put_options", {}).get("market_data", {})

        call_oi = float(c.get("oi",0) or 0)
        put_oi = float(p.get("oi",0) or 0)
        call_chg = oi_change(c)
        put_chg = oi_change(p)

        call_total = call_oi + call_chg
        put_total = put_oi + put_chg
        diff = put_total - call_total

        total_call_oi += call_oi
        total_put_oi += put_oi
        total_call_chg += call_chg
        total_put_chg += put_chg

        if put_chg > call_chg and diff > 0:
            view = "🟢 UP / CALL SIDE"
            card = "bull"
        elif call_chg > put_chg and diff < 0:
            view = "🔴 DOWN / PUT SIDE"
            card = "bear"
        else:
            view = "🟡 WAIT"
            card = "neutral"

        rows.append({
            "strike": strike,
            "atm": strike == atm,
            "call_oi": fmt(call_oi),
            "call_chg": fmt(call_chg),
            "call_total": fmt(call_total),
            "put_total": fmt(put_total),
            "put_chg": fmt(put_chg),
            "put_oi": fmt(put_oi),
            "diff": fmt(diff),
            "call_chg_raw": call_chg,
            "put_chg_raw": put_chg,
            "diff_raw": diff,
            "view": view,
            "card": card
        })

    rows = sorted(rows, key=lambda x: x["strike"])
    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else 0

    overall_diff = total_put_chg - total_call_chg

    if overall_diff > 0 and pcr >= 1:
        decision = "🟢 MARKET UP SIDE / CALL SIDE WATCH"
        color = "#d9fbe6"
    elif overall_diff < 0 and pcr <= 1:
        decision = "🔴 MARKET DOWN SIDE / PUT SIDE WATCH"
        color = "#ffe1e1"
    else:
        decision = "🟡 MIXED / WAIT"
        color = "#fff3cd"

    return jsonify({
        "nifty": nifty,
        "atm": atm,
        "pcr": pcr,
        "expiry": expiry,
        "decision": decision,
        "color": color,
        "call_chg_total": fmt(total_call_chg),
        "put_chg_total": fmt(total_put_chg),
        "diff_total": fmt(overall_diff),
        "rows": rows,
        "time": datetime.now().strftime("%H:%M:%S")
    })

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty Strike Direction</title>
<style>
body{font-family:Arial;background:#f2f4f7;margin:0;padding:8px}
.card{background:white;padding:12px;margin:8px;border-radius:16px;box-shadow:0 2px 6px #ddd}
.top{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.box{background:#f7f8fa;border-radius:14px;padding:10px;text-align:center}
.label{font-size:12px;color:#666}
.val{font-size:20px;font-weight:bold}
.big{font-size:25px;font-weight:bold}
.signal{padding:15px;border-radius:16px;text-align:center;font-size:20px;font-weight:bold;margin:8px}
.green{color:green;font-weight:bold}
.red{color:red;font-weight:bold}
.blue{color:#0754c7;font-weight:bold}
.strikeCard{padding:12px;margin:8px;border-radius:16px;box-shadow:0 2px 6px #ddd}
.bull{background:#e4fbe9;border:2px solid #30b957}
.bear{background:#ffe7e7;border:2px solid #e84b4b}
.neutral{background:#fff5d6;border:2px solid #d9a600}
.atm{box-shadow:0 0 0 3px #ffbf00 inset}
.strikeHead{display:flex;justify-content:space-between;align-items:center}
.strikeNo{font-size:24px;font-weight:bold}
.view{font-size:15px;font-weight:bold}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}
.cell{background:white;border-radius:12px;padding:8px;text-align:center}
.cLabel{font-size:11px;color:#666}
.cVal{font-size:16px;font-weight:bold}
.small{text-align:center;color:#666;font-size:12px}
@media(max-width:420px){
 body{padding:4px}
 .card,.strikeCard{margin:6px;padding:10px}
 .strikeNo{font-size:22px}
 .cVal{font-size:15px}
}
</style>
</head>
<body>

<div class="card">
<div class="top">
<div class="box"><div class="label">NIFTY LIVE</div><div class="big" id="nifty">Loading</div></div>
<div class="box"><div class="label">PCR</div><div class="big" id="pcr">-</div></div>
<div class="box"><div class="label">ATM</div><div class="val" id="atm">-</div></div>
<div class="box"><div class="label">Updated</div><div class="val" id="time">-</div></div>
</div>
</div>

<div class="signal" id="decision">Loading...</div>

<div class="card">
<div class="top">
<div class="box"><div class="label">Total Call Change</div><div class="val red" id="callchg">-</div></div>
<div class="box"><div class="label">Total Put Change</div><div class="val green" id="putchg">-</div></div>
<div class="box"><div class="label">Put - Call Diff</div><div class="val blue" id="diff">-</div></div>
<div class="box"><div class="label">Expiry</div><div class="val" id="expiry">-</div></div>
</div>
</div>

<div id="cards"></div>

<p class="small">ATM ±5 strikes | Auto refresh 2 sec</p>

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
        document.getElementById('pcr').innerText = d.pcr;
        document.getElementById('atm').innerText = d.atm;
        document.getElementById('time').innerText = d.time;
        document.getElementById('expiry').innerText = d.expiry;
        document.getElementById('callchg').innerText = d.call_chg_total;
        document.getElementById('putchg').innerText = d.put_chg_total;
        document.getElementById('diff').innerText = d.diff_total;

        document.getElementById('decision').innerText = d.decision;
        document.getElementById('decision').style.background = d.color;

        let html = "";
        d.rows.forEach(x=>{
            html += `
            <div class="strikeCard ${x.card} ${x.atm ? 'atm' : ''}">
                <div class="strikeHead">
                    <div class="strikeNo">${x.strike}${x.atm ? ' ATM' : ''}</div>
                    <div class="view">${x.view}</div>
                </div>
                <div class="grid">
                    <div class="cell"><div class="cLabel">Call OI</div><div class="cVal red">${x.call_oi}</div></div>
                    <div class="cell"><div class="cLabel">Put OI</div><div class="cVal green">${x.put_oi}</div></div>

                    <div class="cell"><div class="cLabel">Call Change</div><div class="cVal ${x.call_chg_raw<0?'green':'red'}">${x.call_chg}</div></div>
                    <div class="cell"><div class="cLabel">Put Change</div><div class="cVal ${x.put_chg_raw>0?'green':'red'}">${x.put_chg}</div></div>

                    <div class="cell"><div class="cLabel">Call Total</div><div class="cVal red">${x.call_total}</div></div>
                    <div class="cell"><div class="cLabel">Put Total</div><div class="cVal green">${x.put_total}</div></div>

                    <div class="cell" style="grid-column:1/3"><div class="cLabel">Put - Call Difference</div><div class="cVal ${x.diff_raw>=0?'green':'red'}">${x.diff}</div></div>
                </div>
            </div>`;
        });

        document.getElementById('cards').innerHTML = html;

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
