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
        print(item)

        strike = int(

            num(

                item.get(

                    "strike_price"

                )

            )

        )

        if strike not in wanted:

            continue

        call = item.get(

            "call_options",

            {}

        )

        put = item.get(

            "put_options",

            {}

        )

        call_m = call.get(

            "market_data",

            {}

        )

        put_m = put.get(

            "market_data",

            {}

        )

        call_g = call.get(

            "option_greeks",

            {}

        )

        put_g = put.get(

            "option_greeks",

            {}

        )

        call_oi = num(

            call_m.get(

                "oi"

            )

        )

        put_oi = num(

            put_m.get(

                "oi"

            )

        )

        call_prev = num(call_m.get("prev_oi"))
        put_prev = num(put_m.get("prev_oi"))

        call_chg = call_oi - call_prev
        put_chg = put_oi - put_prev

        rows.append(

            {

                "strike": strike,

                "call_oi": call_oi,

                "call_change": call_chg,

                "call_total": call_oi + call_chg,

                "put_oi": put_oi,

                "put_change": put_chg,

                "put_total": put_oi + put_chg,

                "call_iv": num(

                    call_g.get(

                        "iv"

                    )

                ),

                "put_iv": num(

                    put_g.get(

                        "iv"

                    )

                )

            }

        )

    rows.sort(

        key=lambda x: x["strike"]

    )

    return rows
def calculate_flow(rows):

    call_oi = 0

    put_oi = 0

    call_change = 0

    put_change = 0

    call_total = 0

    put_total = 0

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

        "overall_flow": overall

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

font-family:Arial;

margin:20px;

}

h1{

text-align:center;

}

.top{

display:flex;

justify-content:center;

gap:40px;

margin:20px 0;

font-size:22px;

font-weight:bold;

}

table{

width:100%;

border-collapse:collapse;

margin-top:20px;

}

th{

background:#222;

padding:10px;

border:1px solid #444;

}

td{

padding:8px;

border:1px solid #333;

text-align:center;

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

<h1>NIFTY LIVE OPTION DASHBOARD</h1>

<div class="top">

<div>

Spot :
<span id="spot">0</span>

</div>

<div>

ATM :
<span id="atm">0</span>

</div>

<div>

Expiry :
<span id="expiry">-</span>

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

<table>

<thead>

<tr>

<th>CALL OI</th>

<th>CALL ΔOI</th>

<th>CALL TOTAL</th>

<th>STRIKE</th>

<th>PUT TOTAL</th>

<th>PUT ΔOI</th>

<th>PUT OI</th>

</tr>

</thead>

<tbody id="tbody">

</tbody>

</table>

<script>

async function load(){

const r=await fetch("/api");

const d=await r.json();

document.getElementById("spot").innerHTML=d.spot;

document.getElementById("atm").innerHTML=d.atm;

document.getElementById("expiry").innerHTML=d.expiry;

document.getElementById("flow").innerHTML=d.flow.overall_flow;

document.getElementById("callfill").style.width=d.flow.call_bar+"%";

document.getElementById("putfill").style.width=d.flow.put_bar+"%";

let html="";

for(const row of d.rows){

html+=`

<tr>

<td class="call">${Math.round(row.call_oi)}</td>

<td class="call">${Math.round(row.call_change)}</td>

<td class="call">${Math.round(row.call_total)}</td>

<td><b>${row.strike}</b></td>

<td class="put">${Math.round(row.put_total)}</td>

<td class="put">${Math.round(row.put_change)}</td>

<td class="put">${Math.round(row.put_oi)}</td>

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
