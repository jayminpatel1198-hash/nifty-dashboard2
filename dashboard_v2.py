from flask import Flask, jsonify, render_template_string
from datetime import datetime, date
import requests
import time
import os

app = Flask(__name__)

TOKEN = os.environ.get(
    "UPSTOX_TOKEN",
    ""
).strip()

INDEX_KEY = "NSE_INDEX|Nifty 50"

CHAIN_URL = (
    "https://api.upstox.com/v2/option/chain"
)

CONTRACT_URL = (
    "https://api.upstox.com/v2/option/contract"
)

QUOTE_URL = (
    "https://api.upstox.com/v2/market-quote/quotes"
)

STEP = 50

SIDE = 5

TIMEOUT = 15

EXPIRY_CACHE = {

    "expiry": None,

    "time": 0

}


def num(value):

    try:

        return float(value or 0)

    except:

        return 0.0


def short(value):

    value = num(value)

    if abs(value) >= 10000000:

        return f"{value/10000000:.2f}Cr"

    if abs(value) >= 100000:

        return f"{value/100000:.2f}L"

    if abs(value) >= 1000:

        return f"{value/1000:.1f}K"

    return str(round(value))


def headers():

    return {

        "Accept":"application/json",

        "Authorization":

        f"Bearer {TOKEN}"

    }


def get_json(url,params):

    r=requests.get(

        url,

        headers=headers(),

        params=params,

        timeout=TIMEOUT

    )

    data=r.json()

    if r.status_code!=200:

        raise Exception(

            data.get(

                "message",

                "API Error"

            )

        )

    if data.get(

        "status"

    )!="success":

        raise Exception(

            data.get(

                "message",

                "Unknown Error"

            )

        )

    return data
def get_expiry():

    now = time.time()

    if (

        EXPIRY_CACHE["expiry"]

        and

        now - EXPIRY_CACHE["time"] < 300

    ):

        return EXPIRY_CACHE["expiry"]

    data = get_json(

        CONTRACT_URL,

        {

            "instrument_key": INDEX_KEY

        }

    )
    print("INDEX_KEY =", INDEX_KEY)
    print("CONTRACT RESPONSE =", data)

    contracts = data.get("data", [])

    expiries = []

    today = date.today()

    for item in contracts:

        exp = item.get(

            "expiry"

        )

        if not exp:

            continue

        try:

            d = datetime.strptime(

                exp,

                "%Y-%m-%d"

            ).date()

            if d >= today:

                expiries.append(exp)

        except:

            pass

    if not expiries:

        raise Exception(

            "No expiry found"

        )

    expiries = sorted(

        list(

            set(expiries)

        )

    )

    EXPIRY_CACHE["expiry"] = expiries[0]

    EXPIRY_CACHE["time"] = now

    return expiries[0]


def get_spot():

    data = get_json(
        QUOTE_URL,
        {
            "instrument_key": INDEX_KEY
        }
    )

    quotes = data.get("data", {})

    app.logger.info(f"QUOTE RESPONSE = {data}")
    app.logger.info(f"QUOTE KEYS = {list(quotes.keys())}")
    app.logger.info(f"QUOTES = {quotes}")

    if INDEX_KEY in quotes:
        info = quotes[INDEX_KEY]
    elif quotes:
        info = next(iter(quotes.values()))
    else:
        info = {}

    app.logger.info(f"INFO = {info}")

    ltp = num(info.get("last_price"))

    if ltp <= 0:
        ltp = num(info.get("ltp"))

    if ltp <= 0:
        ohlc = info.get("ohlc", {})
        ltp = num(ohlc.get("close"))

    if ltp <= 0:
        return 0

    return ltp

def atm_strike(spot):

    return int(

        round(

            spot / STEP

        ) * STEP

    )


def strike_range(atm):

    return [

        atm + i * STEP

        for i in range(

            -SIDE,

            SIDE + 1

        )

    ]

def get_option_chain(expiry):

    data = get_json(

        CHAIN_URL,

        {

            "instrument_key": INDEX_KEY,
            

            "expiry_date": expiry

        }

    )

    return data.get(

        "data",

        []

    )


def filter_chain(chain, strikes):

    wanted = set(strikes)
    rows = []

    for item in chain:

        strike = int(num(item.get("strike_price")))

        if strike not in wanted:
            continue

        call = item.get("call_options", {})
        put = item.get("put_options", {})

        call_m = call.get("market_data", {})
        put_m = put.get("market_data", {})

        call_g = call.get("option_greeks", {})
        put_g = put.get("option_greeks", {})

        call_oi = num(call_m.get("oi"))
        put_oi = num(put_m.get("oi"))

        call_prev = num(call_m.get("prev_oi"))
        put_prev = num(put_m.get("prev_oi"))

        call_chg = call_oi - call_prev
        put_chg = put_oi - put_prev

        rows.append({

            "strike": strike,

            "call_oi": call_oi,
            "call_change": call_chg,
            "call_total": call_oi + call_chg,

            "put_oi": put_oi,
            "put_change": put_chg,
            "put_total": put_oi + put_chg,

            "call_iv": num(call_g.get("iv")),
            "put_iv": num(put_g.get("iv"))

        })

    rows.sort(key=lambda x: x["strike"])

    if rows:

        max_call = max(rows, key=lambda x: x["call_oi"])["strike"]
        max_put = max(rows, key=lambda x: x["put_oi"])["strike"]

        for r in rows:
            r["resistance"] = (r["strike"] == max_call)
            r["support"] = (r["strike"] == max_put)

    return rows


def calculate_flow(rows):

    call_oi = 0

    put_oi = 0

    call_change = 0

    put_change = 0

    call_total = 0

    put_total = 0
    max_call = max(rows, key=lambda x: x["call_oi"])["strike"]
    max_put = max(rows, key=lambda x: x["put_oi"])["strike"]
    max_pain = min(rows, key=lambda x: abs(x["call_total"] - x["put_total"]))["strike"]
    # -----------------------------
# AI SUPPORT / RESISTANCE ENGINE
# -----------------------------

call_sorted = sorted(
    rows,
    key=lambda x: x["call_total"],
    reverse=True
)

put_sorted = sorted(
    rows,
    key=lambda x: x["put_total"],
    reverse=True
)

major_resistance = call_sorted[0]["strike"]

strong_resistance = (
    call_sorted[1]["strike"]
    if len(call_sorted) > 1
    else major_resistance
)

major_support = put_sorted[0]["strike"]

strong_support = (
    put_sorted[1]["strike"]
    if len(put_sorted) > 1
    else major_support
)

battle_zone = max_pain
    
    for row in rows:

        call_oi += row["call_oi"]

        put_oi += row["put_oi"]

        call_change += row["call_change"]

        put_change += row["put_change"]

        call_total += row["call_total"]

        put_total += row["put_total"]

    total_flow = abs(call_change) + abs(put_change)

    if total_flow == 0:

        call_percent = 50.0

        put_percent = 50.0

    else:

        call_percent = (

            abs(call_change)

            / total_flow

        ) * 100

        put_percent = (

            abs(put_change)

            / total_flow

        ) * 100

    if put_change > call_change:

        overall = "PUT BUYING"

    elif call_change > put_change:

        overall = "CALL WRITING"

    else:

        overall = "NEUTRAL"

    return {

        "call_oi": call_oi,

        "put_oi": put_oi,

        "call_change": call_change,

        "put_change": put_change,

        "call_total": call_total,

        "put_total": put_total,

        "call_bar": round(

            call_percent,

            2

        ),

        "put_bar": round(

            put_percent,

            2

        ),

        "overall_flow": overall,
        "pcr": round(put_oi / call_oi, 2) if call_oi else 0,
        "max_call": max_call,
        "max_put": max_put,
        "trend_score": round((put_percent - call_percent), 1),
        "option_score": round((put_percent / 10), 1),
        "signal":
        (
        "BUY CALL"
        if overall=="PUT BUYING" and put_percent>60
        else
        "BUY PUT"
        if overall=="CALL WRITING" and call_percent>60
        else
        "WAIT"
        ),
        "confidence": round(abs(put_percent-call_percent),1),
        "entry":
        "YES" if abs(put_percent-call_percent)>20 else "NO",

        "exit":
        "YES" if abs(put_percent-call_percent)<8 else "NO",
        "call_strength": round(call_percent,1),
        "put_strength": round(put_percent,1),
        "max_pain": max_pain,
        "s1": max_put,
        "s2": sorted(rows, key=lambda x:x["put_total"], reverse=True)[1]["strike"],
        "r1": max_call,
        "r2": sorted(rows, key=lambda x:x["call_total"], reverse=True)[1]["strike"],
        "major_support": major_support,

        "strong_support": strong_support,

        "major_resistance": major_resistance,

        "strong_resistance": strong_resistance,

        "battle_zone": battle_zone,

    }

@app.route("/api")
def api():

    expiry = get_expiry()

    spot = get_spot()

    atm = atm_strike(

        spot

    )

    strikes = strike_range(

        atm

    )

    chain = get_option_chain(

        expiry

    )

    rows = filter_chain(

        chain,

        strikes

    )

    flow = calculate_flow(

        rows

    )

    return jsonify(

        {

            "time": datetime.now().strftime(

                "%H:%M:%S"

            ),

            "spot": round(

                spot,

                2

            ),

            "atm": atm,

            "expiry": expiry,

            "rows": rows,

            "flow": flow

        }

    )


@app.route("/health")
def health():

    return jsonify(

        {

            "status": "ok",

            "server_time": datetime.now().strftime(

                "%Y-%m-%d %H:%M:%S"

            )

        }

    )

HTML = """
<!DOCTYPE html>
<html>

<head>

<meta charset="utf-8">

<title>NIFTY OI LIVE</title>

<style>

body{
    background:#111;
    color:white;
    font-family:Arial,sans-serif;
    margin:10px;
    padding:0;
    font-size:18px;
}
.card{
    background:#2b2b2b;
    border-radius:12px;
    padding:12px;
    text-align:center;
    box-shadow:0 2px 8px rgba(0,0,0,.4);
}

@media (max-width:768px){

body{
    margin:8px;
}

h1{
    font-size:28px;
}

.top{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:10px;
}

.card{
    padding:14px;
}

.bar{
    height:28px;
}

table{
    font-size:16px;
    min-width:1200px;
}

th,td{
    padding:12px;
}

.table-wrap{
    overflow-x:auto;
    -webkit-overflow-scrolling:touch;
}
}
h1{
    text-align:center;
    font-size:42px;
    margin-bottom:20px;
}

h2{
    text-align:center;
    font-size:32px;
}

h3{
    font-size:28px;
    margin-top:25px;
    margin-bottom:10px;
}

.top{
    display:flex;
    justify-content:center;
    gap:15px;
    flex-wrap:wrap;
    margin-bottom:20px;
}

.top div{
    background:#2b2b2b;
    padding:15px;
    border-radius:12px;
    min-width:180px;
    text-align:center;
    font-size:24px;
    font-weight:bold;
}

h1{

text-align:center;

}

.top-card{
    background:#1b1b1b;
    border-radius:15px;
    padding:15px;
    margin-bottom:20px;
    box-shadow:0 0 10px rgba(255,255,255,.08);
}

.summary{
    display:grid;
    grid-template-columns:repeat(2,1fr);
    gap:12px;
    margin-top:15px;
}

.box{
    background:#2b2b2b;
    border-radius:12px;
    padding:12px;
    text-align:center;
}

.title{
    color:#aaa;
    font-size:14px;
    margin-bottom:6px;
}

.box div:last-child{
    font-size:22px;
    font-weight:bold;
}

@media(min-width:768px){
    .summary{
        grid-template-columns:repeat(4,1fr);
    }
}

table{
    width:100%;
    border-collapse:collapse;
    margin-top:20px;
    font-size:18px;
}

th{
    background:#222;
    padding:14px;
    border:1px solid #444;
    font-size:18px;
}

td{
    padding:12px;
    border:1px solid #333;
    text-align:center;
    font-size:18px;
}

.call{

color:#ff5555;

font-weight:bold;

}

.put{

color:#55ff55;

font-weight:bold;

}

.bar{

width:100%;

height:22px;

background:#333;

border-radius:20px;

overflow:hidden;

margin-top:8px;

}

.fill{

height:100%;

}

#callfill{

background:red;

width:0%;

}

#putfill{

background:limegreen;

width:0%;

}

.flow{

margin-top:20px;

font-size:24px;

text-align:center;

font-weight:bold;

}

</style>

</head>

<body>

<div class="top-card">

<h1>📈 NIFTY LIVE OPTION DASHBOARD</h1>

<div class="summary">

<div class="box">
<div class="title">Spot</div>
<div id="spot">0</div>
</div>

<div class="box">
<div class="title">ATM</div>
<div id="atm">0</div>
</div>

<div class="box">
<div class="title">Expiry</div>
<div id="expiry">-</div>
</div>

<div class="box">
<div class="title">PCR</div>
<div id="pcr">0</div>
</div>
<div class="box">
<div class="title">MAX PAIN</div>
<div id="maxpain">0</div>
<div class="box">
<div class="title">S1</div>
<div id="s1">0</div>
</div>

<div class="box">
<div class="title">S2</div>
<div id="s2">0</div>
</div>

<div class="box">
<div class="title">R1</div>
<div id="r1">0</div>
</div>

<div class="box">
<div class="title">R2</div>
<div id="r2">0</div>
<div class="box">
<div class="title">TREND</div>
<div id="trend">-</div>
</div>

<div class="box">
<div class="title">CONFIDENCE</div>
<div id="confidence">0%</div>
</div>

<div class="box">
<div class="title">SIGNAL</div>
<div id="signal">-</div>
<div class="box">
<div class="title">ENTRY</div>
<div id="entry">-</div>
</div>

<div class="box">
<div class="title">EXIT</div>
<div id="exit">-</div>
</div>
</div>
</div>
</div>

</div>

</div>

<h3>CALL FLOW</h3>

<div class="bar">

<div

id="callfill"

class="fill">

</div>

</div>

<h3>PUT FLOW</h3>

<div class="bar">

<div

id="putfill"

class="fill">

</div>

</div>

<div

class="flow"

id="flow">

Loading...

</div>

<div class="table-wrap">
<table>

<thead>

<tr>

<th>CALL OI</th>
<th>CALL ΔOI</th>
<th>CALL TOTAL</th>
<th>STRIKE</th>
<th>PUT TOTAL</th>
<th>SIGNAL</th>
<th>PUT ΔOI</th>
<th>PUT OI</th>

</tr>

</thead>

<tbody id="tbody">

</tbody>

</table>
</div>
<script>

async function load(){

const r=await fetch("/api");

const d=await r.json();

document.getElementById("spot").innerHTML=d.spot;

document.getElementById("atm").innerHTML=d.atm;

document.getElementById("expiry").innerHTML=d.expiry;
document.getElementById("pcr").innerHTML=d.flow.pcr;
document.getElementById("maxpain").innerHTML=d.flow.max_pain;
document.getElementById("s1").innerHTML=d.flow.s1;
document.getElementById("s2").innerHTML=d.flow.s2;
document.getElementById("r1").innerHTML=d.flow.r1;
document.getElementById("r2").innerHTML=d.flow.r2;
document.getElementById("trend").innerHTML = d.flow.overall_flow;
document.getElementById("confidence").innerHTML = d.flow.confidence + "%";
document.getElementById("signal").innerHTML = d.flow.signal;
document.getElementById("entry").innerHTML=d.flow.entry;
document.getElementById("exit").innerHTML=d.flow.exit;

document.getElementById("flow").innerHTML=d.flow.overall_flow;

document.getElementById("callfill").style.width=d.flow.call_bar+"%";

document.getElementById("putfill").style.width=d.flow.put_bar+"%";

let html="";

for(const row of d.rows){

html+=`

<tr>

<td class="call">
<div style="display:flex;align-items:center;gap:5px;">
<div style="height:10px;background:red;width:${Math.min(row.call_oi/50000,250)}px;border-radius:5px;"></div>
<span>${Math.round(row.call_oi)}</span>
</div>
</td>

<td class="call">${Math.round(row.call_change)}</td>

<td class="call">${Math.round(row.call_total)}</td>

<td style="
background:${row.strike==d.atm ? '#ffd70033' : ''};
color:${row.strike==d.atm ? 'yellow' : 'white'};
font-weight:bold;
font-size:18px;
">
${
row.resistance
? "🔴 "+row.strike
: row.support
? "🟢 "+row.strike
: row.strike==d.atm
? "🟡 "+row.strike
: row.strike
}
</td>


<td class="put">${Math.round(row.put_total)}</td>

<td class="signal">
${
row.call_change > 0 && row.put_change < 0 ? "🔴 CALL WRITING" :
row.put_change > 0 && row.call_change < 0 ? "🟢 PUT WRITING" :
row.call_change > 0 && row.put_change > 0 ? "⚡ LONG BUILDUP" :
row.call_change < 0 && row.put_change < 0 ? "🟡 SHORT COVERING" :
"➖ NEUTRAL"
}
</td>

<td class="put">${Math.round(row.put_change)}</td>

<td class="put">
<div style="display:flex;align-items:center;gap:5px;">
<div style="height:10px;background:limegreen;width:${Math.min(row.put_oi/50000,250)}px;border-radius:5px;"></div>
<span>${Math.round(row.put_oi)}</span>
</div>
</td>

</tr>

`;

}

document.getElementById("tbody").innerHTML=html;

}

load();

setInterval(

load,

5000

);

</script>

</body>

</html>
"""

@app.route("/")
def home():

    return render_template_string(
        HTML
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
