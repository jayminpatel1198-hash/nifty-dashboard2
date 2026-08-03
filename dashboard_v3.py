from flask import Flask, jsonify, render_template_string
from datetime import datetime, date
import requests
import time
import os

app = Flask(__name__)

TOKEN = os.environ.get("UPSTOX_TOKEN", "").strip()

INDEX_KEY = "NSE_INDEX|Nifty 50"

CHAIN_URL = "https://api.upstox.com/v2/option/chain"
CONTRACT_URL = "https://api.upstox.com/v2/option/contract"
QUOTE_URL = "https://api.upstox.com/v2/market-quote/quotes"

STEP = 50
SIDE = 5
TIMEOUT = 15

EXPIRY_CACHE = {
    "expiry": None,
    "time": 0
}


def num(v):
    try:
        return float(v or 0)
    except:
        return 0.0


def headers():
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }
  def get_json(url, params):

    r = requests.get(
        url,
        headers=headers(),
        params=params,
        timeout=TIMEOUT
    )

    data = r.json()

    if r.status_code != 200:
        raise Exception(
            data.get(
                "message",
                "API Error"
            )
        )

    if data.get("status") != "success":
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

    contracts = data.get("data", [])

    expiries = []

    today = date.today()

    for item in contracts:

        exp = item.get("expiry")

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

    expiries = sorted(
        list(set(expiries))
    )

    if not expiries:
        raise Exception("No expiry")

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

    if INDEX_KEY in quotes:
        info = quotes[INDEX_KEY]
    elif quotes:
        info = next(iter(quotes.values()))
    else:
        info = {}

    ltp = num(info.get("last_price"))

    if ltp <= 0:
        ltp = num(info.get("ltp"))

    if ltp <= 0:
        ltp = num(
            info.get(
                "ohlc",
                {}
            ).get(
                "close"
            )
        )

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

        call_oi = num(

            call_m.get("oi")

        )

        put_oi = num(

            put_m.get("oi")

        )

        call_prev = num(

            call_m.get("prev_oi")

        )

        put_prev = num(

            put_m.get("prev_oi")

        )

        call_change = call_oi - call_prev

        put_change = put_oi - put_prev

        rows.append({

            "strike": strike,

            "call_oi": call_oi,

            "call_change": call_change,

            "call_total": call_oi + call_change,

            "put_oi": put_oi,

            "put_change": put_change,

            "put_total": put_oi + put_change

        })

    rows.sort(

        key=lambda x: x["strike"]

    )

    return rows

def calculate_flow(rows):

    if not rows:
        return {}

    call_oi = sum(r["call_oi"] for r in rows)
    put_oi = sum(r["put_oi"] for r in rows)

    call_change = sum(r["call_change"] for r in rows)
    put_change = sum(r["put_change"] for r in rows)

    call_total = sum(r["call_total"] for r in rows)
    put_total = sum(r["put_total"] for r in rows)

    max_call = max(rows, key=lambda x: x["call_oi"])["strike"]
    max_put = max(rows, key=lambda x: x["put_oi"])["strike"]

    max_pain = min(
        rows,
        key=lambda x: abs(
            x["call_total"] - x["put_total"]
        )
    )["strike"]

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

    r1 = call_sorted[0]["strike"]
    r2 = call_sorted[1]["strike"] if len(call_sorted) > 1 else r1

    s1 = put_sorted[0]["strike"]
    s2 = put_sorted[1]["strike"] if len(put_sorted) > 1 else s1

    total_flow = abs(call_change) + abs(put_change)

    if total_flow == 0:
        call_percent = 50
        put_percent = 50
    else:
        call_percent = abs(call_change) / total_flow * 100
        put_percent = abs(put_change) / total_flow * 100

    trend_score = round(put_percent - call_percent, 1)

    if trend_score > 20:
        ai_signal = "🚀 STRONG BULLISH"
    elif trend_score > 10:
        ai_signal = "🟢 BULLISH"
    elif trend_score < -20:
        ai_signal = "🔻 STRONG BEARISH"
    elif trend_score < -10:
        ai_signal = "🔴 BEARISH"
    else:
        ai_signal = "🟡 SIDEWAYS"

    return {

        "call_oi": call_oi,
        "put_oi": put_oi,

        "call_change": call_change,
        "put_change": put_change,

        "call_total": call_total,
        "put_total": put_total,

        "call_bar": round(call_percent,2),
        "put_bar": round(put_percent,2),

        "overall_flow": ai_signal,

        "pcr": round(
            put_oi/call_oi,
            2
        ) if call_oi else 0,

        "max_pain": max_pain,

        "s1": s1,
        "s2": s2,

        "r1": r1,
        "r2": r2,

        "confidence": round(abs(trend_score)*3,1),

        "trend_score": trend_score,

        "buy_score": round(put_percent),

        "sell_score": round(call_percent)

    }
  @app.route("/api")
def api():

    expiry = get_expiry()

    spot = get_spot()

    atm = atm_strike(spot)

    strikes = strike_range(atm)

    chain = get_option_chain(expiry)

    rows = filter_chain(chain, strikes)

    flow = calculate_flow(rows)

    return jsonify({

        "time": datetime.now().strftime("%H:%M:%S"),

        "spot": round(spot,2),

        "atm": atm,

        "expiry": expiry,

        "rows": rows,

        "flow": flow

    })


@app.route("/health")
def health():

    return jsonify({

        "status":"ok",

        "time":datetime.now().strftime("%H:%M:%S")

    })
