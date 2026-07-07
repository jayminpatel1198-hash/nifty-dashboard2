from flask import Flask, render_template_string
from markupsafe import Markup
import requests, os
from datetime import datetime

app = Flask(__name__)
TOKEN = os.environ.get("UPSTOX_TOKEN")

UNDERLYING = "NSE_INDEX|Nifty 50"
EXPIRY = "current_week"

HTML = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="10">
<title>Nifty OI Dashboard</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0;padding:8px}
.card{background:white;padding:12px;margin:7px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.big{font-size:24px;font-weight:bold}
.green{color:green;font-weight:bold}
.red{color:red;font-weight:bold}
.signal{padding:16px;border-radius:16px;text-align:center;font-size:23px;font-weight:bold;margin:7px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.box{background:#f8f9fa;border-radius:12px;padding:9px;text-align:center}
.label{font-size:12px;color:#555}
.val{font-size:18px;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:12px}
td,th{padding:6px;border-bottom:1px solid #ddd;text-align:right}
td:first-child,th:first-child{text-align:left}
.small{text-align:center;color:#555;font-size:12px}
</style>
</head>
<body>

<div class="card">NIFTY LIVE: <span class="big">{{ nifty_price }}</span></div>

<div class="signal" style="background:{{ color }}">{{ decision }}</div>

<div class="card">
<div class="grid">
<div class="box"><div class="label">Highest Call OI Resistance</div><div class="val red">{{ high_call_oi_strike }}</div></div>
<div class="box"><div class="label">Highest Put OI Support</div><div class="val green">{{ high_put_oi_strike }}</div></div>
<div class="box"><div class="label">Highest Call OI Change</div><div class="val red">{{ high_call_chg_strike }}</div></div>
<div class="box"><div class="label">Highest Put OI Change</div><div class="val green">{{ high_put_chg_strike }}</div></div>
<div class="box"><div class="label">Total Call OI</div><div class="val red">{{ total_call_oi }}</div></div>
<div class="box"><div class="label">Total Put OI</div><div class="val green">{{ total_put_oi }}</div></div>
<div class="box"><div class="label">Total Call OI Chg</div><div class="val red">{{ total_call_chg }}</div></div>
<div class="box"><div class="label">Total Put OI Chg</div><div class="val green">{{ total_put_chg }}</div></div>
</div>
</div>

<div class="card">
<h3>Live Option Chain OI</h3>
<table>
<tr>
<th>Strike</th>
<th>Call OI</th>
<th>Call Chg OI</th>
<th>Put Chg OI</th>
<th>Put OI</th>
</tr>
{{ rows }}
</table>
</div>

<p class="small">Auto refresh 10 sec | Expiry: {{ expiry }} | Updated: {{ time }}</p>

</body>
</html>
"""

def fmt(n):
    try:
        n = float(n)
        if abs(n) >= 10000000:
            return str(round(n / 10000000, 2)) + "Cr"
        if abs(n) >= 100000:
            return str(round(n / 100000, 2)) + "L"
        if abs(n) >= 1000:
            return str(round(n / 1000, 1)) + "K"
        return str(int(n))
    except:
        return "-"

def make_rows(items):
    out = ""
    for r in items:
        cc = "green" if r["call_chg"] < 0 else "red"
        pc = "green" if r["put_chg"] > 0 else "red"
        out += f"""
        <tr>
            <td>{r['strike']}</td>
            <td class='red'>{fmt(r['call_oi'])}</td>
            <td class='{cc}'>{fmt(r['call_chg'])}</td>
            <td class='{pc}'>{fmt(r['put_chg'])}</td>
            <td class='green'>{fmt(r['put_oi'])}</td>
        </tr>
        """
    return Markup(out)

@app.route("/")
def home():
    if not TOKEN:
        return "UPSTOX_TOKEN missing"

    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer " + TOKEN
    }

    nifty_price = "Error"

    try:
        ltp_res = requests.get(
            "https://api.upstox.com/v2/market-quote/ltp",
            headers=headers,
            params={"instrument_key": UNDERLYING},
            timeout=10
        )
        ltp_json = ltp_res.json()
        nifty_price = ltp_json["data"]["NSE_INDEX:Nifty 50"]["last_price"]
    except:
        pass

    try:
        oc_res = requests.get(
            "https://api.upstox.com/v2/option/chain",
            headers=headers,
            params={
                "instrument_key": UNDERLYING,
                "expiry_date": EXPIRY
            },
            timeout=15
        )

        js = oc_res.json()

        if js.get("status") != "success":
            return "Option Chain API Error: " + str(js)

        data = js.get("data", [])

    except Exception as e:
        return "Option Chain Error: " + str(e)

    rows = []
    total_call_oi = 0
    total_put_oi = 0
    total_call_chg = 0
    total_put_chg = 0

    for x in data:
        strike = x.get("strike_price", 0)

        call_md = x.get("call_options", {}).get("market_data", {})
        put_md = x.get("put_options", {}).get("market_data", {})

        call_oi = call_md.get("oi", 0) or 0
        put_oi = put_md.get("oi", 0) or 0

        call_chg = call_md.get("oi_day_change", 0) or call_md.get("oi_change", 0) or call_md.get("change_oi", 0) or 0
        put_chg = put_md.get("oi_day_change", 0) or put_md.get("oi_change", 0) or put_md.get("change_oi", 0) or 0

        total_call_oi += call_oi
        total_put_oi += put_oi
        total_call_chg += call_chg
        total_put_chg += put_chg

        rows.append({
            "strike": int(strike),
            "call_oi": call_oi,
            "call_chg": call_chg,
            "put_chg": put_chg,
            "put_oi": put_oi
        })

    if not rows:
        return "No option chain data found."

    rows = sorted(rows, key=lambda x: x["strike"])

    high_call_oi = max(rows, key=lambda x: x["call_oi"])
    high_put_oi = max(rows, key=lambda x: x["put_oi"])
    high_call_chg = max(rows, key=lambda x: x["call_chg"])
    high_put_chg = max(rows, key=lambda x: x["put_chg"])

    # Simple OI decision
    if total_put_chg > total_call_chg and total_put_oi > total_call_oi:
        decision = "🟢 OI BULLISH - PUT WRITING STRONG"
        color = "#d9fbe6"
    elif total_call_chg > total_put_chg and total_call_oi > total_put_oi:
        decision = "🔴 OI BEARISH - CALL WRITING STRONG"
        color = "#ffe1e1"
    else:
        decision = "🟡 OI MIXED / WAIT"
        color = "#fff3cd"

    return render_template_string(
        HTML,
        nifty_price=nifty_price,
        decision=decision,
        color=color,
        high_call_oi_strike=high_call_oi["strike"],
        high_put_oi_strike=high_put_oi["strike"],
        high_call_chg_strike=high_call_chg["strike"],
        high_put_chg_strike=high_put_chg["strike"],
        total_call_oi=fmt(total_call_oi),
        total_put_oi=fmt(total_put_oi),
        total_call_chg=fmt(total_call_chg),
        total_put_chg=fmt(total_put_chg),
        rows=make_rows(rows),
        expiry=EXPIRY,
        time=datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    )
