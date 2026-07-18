from flask import Flask, jsonify, render_template_string
from datetime import datetime
import os
import requests

app = Flask(__name__)

TOKEN = os.environ.get("UPSTOX_TOKEN", "").strip()
INDEX_KEY = "NSE_INDEX|Nifty 50"
URL = "https://api.upstox.com/v2/option/chain"
STEP = 50
SIDE = 5


def number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def short(value):
    value = number(value)

    if abs(value) < 0.5:
        return "0"

    sign = "+" if value > 0 else "-"
    value = abs(value)

    if value >= 10000000:
        return f"{sign}{value / 10000000:.2f}Cr"
    if value >= 100000:
        return f"{sign}{value / 100000:.2f}L"
    if value >= 1000:
        return f"{sign}{value / 1000:.1f}K"

    return f"{sign}{value:.0f}"


def oi_change(market):
    for key in (
        "oi_day_change",
        "oi_change",
        "change_oi",
        "change_in_oi",
        "oi_change_value",
    ):
        value = market.get(key)

        if value not in (None, ""):
            return number(value)

    current = number(market.get("oi"))

    previous = number(
        market.get("prev_oi")
        or market.get("previous_oi")
        or market.get("close_oi")
        or 0
    )

    return current - previous if previous else 0.0


def fetch_chain():
    if not TOKEN:
        raise RuntimeError(
            "UPSTOX_TOKEN missing છે."
        )

    response = requests.get(
        URL,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        },
        params={
            "instrument_key": INDEX_KEY,
            "expiry_date": "current_week",
        },
        timeout=15,
    )

    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError(
            f"Upstox response error: {response.status_code}"
        )

    if response.status_code == 401:
        raise RuntimeError(
            "UPSTOX_TOKEN invalid અથવા expired છે."
        )

    if not response.ok:
        raise RuntimeError(
            payload.get("message")
            or f"Upstox error {response.status_code}"
        )

    data = payload.get("data", [])

    if not data:
        raise RuntimeError(
            "Current-week option-chain data મળ્યો નથી."
        )

    return data


def prepare_row(item, atm):
    strike = int(number(item.get("strike_price")))

    call_market = (
        item.get("call_options", {})
        .get("market_data", {})
    )

    put_market = (
        item.get("put_options", {})
        .get("market_data", {})
    )

    call_oi = number(call_market.get("oi"))
    put_oi = number(put_market.get("oi"))

    call_change = oi_change(call_market)
    put_change = oi_change(put_market)

    call_total = call_oi + call_change
    put_total = put_oi + put_change

    return {
        "strike": strike,
        "atm": strike == atm,

        "call_oi_raw": call_oi,
        "call_change_raw": call_change,
        "call_total_raw": call_total,

        "put_oi_raw": put_oi,
        "put_change_raw": put_change,
        "put_total_raw": put_total,

        "call_oi": short(call_oi),
        "call_change": short(call_change),
        "call_total": short(call_total),

        "put_oi": short(put_oi),
        "put_change": short(put_change),
        "put_total": short(put_total),
    }


@app.route("/api")
def api():
    try:
        chain = fetch_chain()

        nifty = 0.0
        expiry = "current_week"

        for item in chain:
            spot = number(
                item.get("underlying_spot_price")
            )

            if spot > 0:
                nifty = spot

            if item.get("expiry"):
                expiry = item.get("expiry")

            if nifty > 0:
                break

        if nifty <= 0:
            raise RuntimeError(
                "NIFTY live price મળ્યો નથી."
            )

        atm = int(round(nifty / STEP) * STEP)

        needed = {atm}

        for count in range(1, SIDE + 1):
            needed.add(atm + count * STEP)
            needed.add(atm - count * STEP)

        strike_map = {}

        for item in chain:
            strike = int(
                number(item.get("strike_price"))
            )

            if strike in needed:
                strike_map[strike] = prepare_row(
                    item,
                    atm,
                )

        if atm not in strike_map:
            raise RuntimeError(
                "ATM strike data મળ્યો નથી."
            )

        upper = []
        lower = []

        for count in range(1, SIDE + 1):
            upper_strike = atm + count * STEP
            lower_strike = atm - count * STEP

            if upper_strike in strike_map:
                upper.append(strike_map[upper_strike])

            if lower_strike in strike_map:
                lower.append(strike_map[lower_strike])

        if not upper or not lower:
            raise RuntimeError(
                "ATM આસપાસના strikes મળ્યા નથી."
            )

        resistance = max(
            upper,
            key=lambda row: row["call_total_raw"],
        )

        support = max(
            lower,
            key=lambda row: row["put_total_raw"],
        )

        pairs = []

        for index in range(SIDE):
            pairs.append({
                "upper": (
                    upper[index]
                    if index < len(upper)
                    else None
                ),
                "lower": (
                    lower[index]
                    if index < len(lower)
                    else None
                ),
            })

        return jsonify({
            "nifty": round(nifty, 2),
            "atm": atm,
            "expiry": expiry,
            "time": datetime.now().strftime("%H:%M:%S"),

            "atm_data": strike_map[atm],
            "pairs": pairs,

            "resistance": {
                "strike": resistance["strike"],
                "oi": resistance["call_oi"],
                "change": resistance["call_change"],
                "total": resistance["call_total"],
            },

            "support": {
                "strike": support["strike"],
                "oi": support["put_oi"],
                "change": support["put_change"],
                "total": support["put_total"],
            },
        })

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


HTML = """
<!doctype html>
<html lang="gu">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NIFTY OI</title>

<style>
*{box-sizing:border-box}
body{margin:0;padding:5px;background:#f2f4f7;font-family:Arial}
.card{background:white;border-radius:14px;padding:10px;margin:7px 1px;box-shadow:0 2px 7px #ccc}
.top{display:flex;justify-content:space-between;align-items:center}
.price{font-size:27px;font-weight:900}
.info{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:9px}
.info div{background:#f5f7f9;text-align:center;padding:7px 2px;border-radius:9px}
.label{font-size:9px;color:#666}
.value{font-size:14px;font-weight:900}
.red{color:#d71919}.green{color:#078524}
.atm{background:#fff4c9;border:3px solid #d9a300}
.title{text-align:center;font-size:20px;font-weight:900;margin-bottom:7px}
.two,.pair,.levels{display:grid;grid-template-columns:1fr 1fr;gap:5px}
.side,.strike,.level{border-radius:10px;padding:7px 3px;text-align:center}
.call{background:#fff0f0}.put{background:#eaf9ed}
.line{display:flex;justify-content:space-between;font-size:11px;padding:3px 1px}
.total{margin-top:4px;padding:5px 1px;border-radius:7px;font-size:13px;font-weight:900}
.calltotal{background:#ffdada;color:#c60000}
.puttotal{background:#d7f4dd;color:#007b21}
.head{font-weight:900;text-align:center;padding:7px;border-radius:9px;margin-bottom:5px}
.reshead{background:#ffe1e1;color:#c60000}.suphead{background:#def6e3;color:#007b21}
.pair{margin:6px 0}
.strike{background:#f8f9fa;border:1px solid #ddd}
.resstrike{border-left:4px solid #db2424}.supstrike{border-right:4px solid #148d35}
.strikenum{font-size:17px;font-weight:900;margin-bottom:5px}
.mini{display:grid;grid-template-columns:1fr 1fr;gap:3px}
.mini div{border-radius:7px;padding:5px 2px}
.mcall{background:#fff0f0}.mput{background:#eaf9ed}
.small{font-size:9px}.smallval{font-size:10px;font-weight:900}
.level{padding:11px 4px}
.reslevel{background:#ffe3e3;border:2px solid #db2424}
.suplevel{background:#e1f7e6;border:2px solid #148d35}
.levelstrike{font-size:25px;font-weight:900}
.error{display:none;background:#ffe1e1;color:#a00000;text-align:center;font-weight:800}
</style>
</head>

<body>

<div class="card">
    <div class="top">
        <span>NIFTY LIVE</span>
        <span class="price" id="nifty">Loading...</span>
    </div>

    <div class="info">
        <div>
            <span class="label">ATM</span>
            <div class="value" id="atm">-</div>
        </div>

        <div>
            <span class="label">Expiry</span>
            <div class="value" id="expiry">-</div>
        </div>

        <div>
            <span class="label">Updated</span>
            <div class="value" id="time">-</div>
        </div>
    </div>
</div>

<div class="card error" id="error"></div>

<div class="card atm">
    <div class="title" id="atmTitle">ATM -</div>

    <div class="two">
        <div class="side call">
            <b class="red">ATM CALL</b>
            <div class="line">
                <span>OI</span>
                <b id="atmCallOi">-</b>
            </div>
            <div class="line">
                <span>Change</span>
                <b id="atmCallChange">-</b>
            </div>
            <div class="total calltotal" id="atmCallTotal">
                Total -
            </div>
        </div>

        <div class="side put">
            <b class="green">ATM PUT</b>
            <div class="line">
                <span>OI</span>
                <b id="atmPutOi">-</b>
            </div>
            <div class="line">
                <span>Change</span>
                <b id="atmPutChange">-</b>
            </div>
            <div class="total puttotal" id="atmPutTotal">
                Total -
            </div>
        </div>
    </div>
</div>

<div class="card">
    <div class="two">
        <div class="head reshead">RESISTANCE SIDE</div>
        <div class="head suphead">SUPPORT SIDE</div>
    </div>

    <div id="pairs"></div>
</div>

<div class="card">
    <div class="levels">
        <div class="level reslevel">
            <b class="red">RESISTANCE</b>
            <div class="levelstrike red" id="resStrike">-</div>
            <div id="resDetail">-</div>
        </div>

        <div class="level suplevel">
            <b class="green">SUPPORT</b>
            <div class="levelstrike green" id="supStrike">-</div>
            <div id="supDetail">-</div>
        </div>
    </div>
</div>

<script>
function color(value){
    value=Number(value||0);
    if(value>0)return "green";
    if(value<0)return "red";
    return "";
}

function strikeBox(row,type){
    if(!row)return "<div class='strike'>Data નથી</div>";

    return `
    <div class="strike ${type}">
        <div class="strikenum">${row.strike}</div>

        <div class="mini">
            <div class="mcall">
                <b class="red small">CALL</b>
                <div class="small">OI</div>
                <div class="smallval red">${row.call_oi}</div>
                <div class="small">Change</div>
                <div class="smallval ${color(row.call_change_raw)}">
                    ${row.call_change}
                </div>
                <div class="total calltotal">
                    ${row.call_total}
                </div>
            </div>

            <div class="mput">
                <b class="green small">PUT</b>
                <div class="small">OI</div>
                <div class="smallval green">${row.put_oi}</div>
                <div class="small">Change</div>
                <div class="smallval ${color(row.put_change_raw)}">
                    ${row.put_change}
                </div>
                <div class="total puttotal">
                    ${row.put_total}
                </div>
            </div>
        </div>
    </div>`;
}

async function load(){
    const errorBox=document.getElementById("error");

    try{
        const response=await fetch(
            "/api?t="+Date.now(),
            {cache:"no-store"}
        );

        const data=await response.json();

        if(!response.ok||data.error){
            throw new Error(data.error||"Load failed");
        }

        errorBox.style.display="none";

        nifty.innerText=data.nifty;
        atm.innerText=data.atm;
        expiry.innerText=data.expiry;
        time.innerText=data.time;
        atmTitle.innerText="ATM "+data.atm;

        const a=data.atm_data;

        atmCallOi.innerText=a.call_oi;
        atmCallChange.innerText=a.call_change;
        atmCallChange.className=color(a.call_change_raw);
        atmCallTotal.innerText="Total "+a.call_total;

        atmPutOi.innerText=a.put_oi;
        atmPutChange.innerText=a.put_change;
        atmPutChange.className=color(a.put_change_raw);
        atmPutTotal.innerText="Total "+a.put_total;

        pairs.innerHTML=data.pairs.map(pair=>`
            <div class="pair">
                ${strikeBox(pair.upper,"resstrike")}
                ${strikeBox(pair.lower,"supstrike")}
            </div>
        `).join("");

        resStrike.innerText=data.resistance.strike;
        resDetail.innerHTML=
            "Call OI "+data.resistance.oi+
            "<br>Change "+data.resistance.change+
            "<br><b class='red'>Total "+data.resistance.total+"</b>";

        supStrike.innerText=data.support.strike;
        supDetail.innerHTML=
            "Put OI "+data.support.oi+
            "<br>Change "+data.support.change+
            "<br><b class='green'>Total "+data.support.total+"</b>";

    }catch(error){
        errorBox.style.display="block";
        errorBox.innerText=error.message;
    }
}

load();
setInterval(load,3000);
</script>

</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "token_configured": bool(TOKEN),
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
        )
