from flask import Flask, jsonify, render_template_string
from datetime import datetime, date
import os
import requests


app = Flask(__name__)


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.environ.get("UPSTOX_TOKEN", "").strip()

UNDERLYING = "NSE_INDEX|Nifty 50"
STRIKE_STEP = 50
STRIKES_EACH_SIDE = 5
TIMEOUT = 18

OPTION_CHAIN_URL = "https://api.upstox.com/v2/option/chain"
OPTION_CONTRACT_URL = "https://api.upstox.com/v2/option/contract"


# =========================================================
# HELPERS
# =========================================================

def headers():
    if not TOKEN:
        raise RuntimeError(
            "UPSTOX_TOKEN missing છે. Render Environmentમાં token add કરો."
        )

    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {TOKEN}",
    }


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def fmt(value):
    number = safe_float(value)

    if abs(number) < 0.5:
        return "0"

    sign = "+" if number > 0 else "-"
    number = abs(number)

    if number >= 10_000_000:
        return f"{sign}{number / 10_000_000:.2f}Cr"

    if number >= 100_000:
        return f"{sign}{number / 100_000:.2f}L"

    if number >= 1_000:
        return f"{sign}{number / 1_000:.1f}K"

    return f"{sign}{number:.0f}"


def extract_error(payload, default_message):
    if not isinstance(payload, dict):
        return default_message

    if payload.get("message"):
        return str(payload["message"])

    errors = payload.get("errors")

    if isinstance(errors, list) and errors:
        first = errors[0]

        if isinstance(first, dict):
            return str(
                first.get("message")
                or first.get("errorCode")
                or first
            )

        return str(first)

    return default_message


def request_json(url, params):
    try:
        response = requests.get(
            url,
            headers=headers(),
            params=params,
            timeout=TIMEOUT,
        )
    except requests.Timeout:
        raise RuntimeError("Upstox API timeout. ફરી refresh કરો.")
    except requests.RequestException as error:
        raise RuntimeError(f"Upstox connection error: {error}")

    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError(
            f"Upstox invalid response મળ્યો. HTTP {response.status_code}"
        )

    if response.status_code == 401:
        raise RuntimeError(
            "UPSTOX_TOKEN માન્ય નથી અથવા expire થયો છે. "
            "Analytics Token ફરી copy કરીને Renderમાં update કરો."
        )

    if not response.ok:
        raise RuntimeError(
            extract_error(
                payload,
                f"Upstox API HTTP {response.status_code}",
            )
        )

    if payload.get("status") != "success":
        raise RuntimeError(
            extract_error(payload, "Upstox API request failed")
        )

    return payload


def calculate_oi_change(market_data):
    """
    Upstox option-chain market_dataમાંથી OI change કાઢે છે.
    પહેલાં direct change field તપાસે છે.
    પછી current OI - previous OI કરે છે.
    """

    direct_keys = [
        "oi_day_change",
        "oi_change",
        "change_oi",
        "change_in_oi",
        "oi_change_value",
    ]

    for key in direct_keys:
        value = market_data.get(key)

        if value not in (None, ""):
            return safe_float(value)

    current_oi = safe_float(market_data.get("oi"))

    previous_oi = safe_float(
        market_data.get("prev_oi")
        or market_data.get("previous_oi")
        or market_data.get("close_oi")
        or 0
    )

    if previous_oi:
        return current_oi - previous_oi

    return 0.0


# =========================================================
# EXPIRY SELECTION
# =========================================================

def get_active_expiries():
    """
    Option Contracts APIમાંથી active NIFTY expiries શોધે છે.
    """

    payload = request_json(
        OPTION_CONTRACT_URL,
        {
            "instrument_key": UNDERLYING,
        },
    )

    expiries = set()

    for contract in payload.get("data", []):
        expiry = contract.get("expiry")

        if expiry:
            expiries.add(str(expiry))

    if not expiries:
        return []

    today_text = date.today().isoformat()

    return sorted(
        expiry
        for expiry in expiries
        if expiry >= today_text
    )


def try_option_chain(expiry_value):
    """
    આપેલી expiry માટે option chain માંગે છે.
    Data ન હોય તો None return કરે છે.
    """

    try:
        payload = request_json(
            OPTION_CHAIN_URL,
            {
                "instrument_key": UNDERLYING,
                "expiry_date": expiry_value,
            },
        )
    except RuntimeError:
        return None

    data = payload.get("data", [])

    if not data:
        return None

    return data


def fetch_option_chain():
    """
    Expiry selection sequence:

    1. current_week
    2. active actual dates from option contracts
    3. next_week
    4. current_month
    """

    attempts = []

    for keyword in [
        "current_week",
        "next_week",
        "current_month",
    ]:
        attempts.append(keyword)

    try:
        active_expiries = get_active_expiries()
    except RuntimeError:
        active_expiries = []

    # Actual datesને keyword પછી નહીં પરંતુ current_week પછી priority આપવી.
    ordered_attempts = ["current_week"]

    ordered_attempts.extend(
        expiry
        for expiry in active_expiries[:8]
        if expiry not in ordered_attempts
    )

    for keyword in ["next_week", "current_month"]:
        if keyword not in ordered_attempts:
            ordered_attempts.append(keyword)

    for expiry_value in ordered_attempts:
        chain = try_option_chain(expiry_value)

        if chain:
            actual_expiry = (
                chain[0].get("expiry")
                or expiry_value
            )

            return chain, actual_expiry

    raise RuntimeError(
        "કોઈ active NIFTY Option Chain data મળ્યો નથી. "
        "Token અથવા Upstox API response check કરો."
    )


# =========================================================
# API ROUTE
# =========================================================

@app.route("/api")
def api():
    try:
        chain, selected_expiry = fetch_option_chain()

        nifty_price = 0.0

        for item in chain:
            spot = safe_float(
                item.get("underlying_spot_price")
            )

            if spot > 0:
                nifty_price = spot
                break

        if nifty_price <= 0:
            raise RuntimeError("NIFTY live price મળ્યો નથી.")

        atm = int(
            round(nifty_price / STRIKE_STEP)
            * STRIKE_STEP
        )

        lowest_strike = (
            atm
            - STRIKES_EACH_SIDE
            * STRIKE_STEP
        )

        highest_strike = (
            atm
            + STRIKES_EACH_SIDE
            * STRIKE_STEP
        )

        rows = []

        total_call_oi = 0.0
        total_put_oi = 0.0
        total_call_change = 0.0
        total_put_change = 0.0

        for item in chain:
            strike = int(
                safe_float(
                    item.get("strike_price")
                )
            )

            if strike < lowest_strike or strike > highest_strike:
                continue

            call_market = (
                item.get("call_options", {})
                .get("market_data", {})
            )

            put_market = (
                item.get("put_options", {})
                .get("market_data", {})
            )

            call_oi = safe_float(
                call_market.get("oi")
            )

            put_oi = safe_float(
                put_market.get("oi")
            )

            call_change = calculate_oi_change(
                call_market
            )

            put_change = calculate_oi_change(
                put_market
            )

            call_total = call_oi + call_change
            put_total = put_oi + put_change

            total_call_oi += call_oi
            total_put_oi += put_oi
            total_call_change += call_change
            total_put_change += put_change

            rows.append({
                "strike": strike,
                "atm": strike == atm,

                "call_oi_raw": call_oi,
                "call_change_raw": call_change,
                "call_total_raw": call_total,

                "put_oi_raw": put_oi,
                "put_change_raw": put_change,
                "put_total_raw": put_total,

                "call_oi": fmt(call_oi),
                "call_change": fmt(call_change),
                "call_total": fmt(call_total),

                "put_oi": fmt(put_oi),
                "put_change": fmt(put_change),
                "put_total": fmt(put_total),
            })

        rows.sort(
            key=lambda row: row["strike"]
        )

        if len(rows) < 3:
            raise RuntimeError(
                "ATM નજીક પૂરતો strike data મળ્યો નથી."
            )

        # Resistance માત્ર ATM અને ઉપરના strikesમાંથી.
        resistance_candidates = [
            row
            for row in rows
            if row["strike"] >= atm
        ]

        # Support માત્ર ATM અને નીચેના strikesમાંથી.
        support_candidates = [
            row
            for row in rows
            if row["strike"] <= atm
        ]

        if not resistance_candidates:
            resistance_candidates = rows

        if not support_candidates:
            support_candidates = rows

        resistance_ranked = sorted(
            resistance_candidates,
            key=lambda row: (
                row["call_total_raw"],
                row["call_oi_raw"],
            ),
            reverse=True,
        )[:3]

        support_ranked = sorted(
            support_candidates,
            key=lambda row: (
                row["put_total_raw"],
                row["put_oi_raw"],
            ),
            reverse=True,
        )[:3]

        strongest_resistance = resistance_ranked[0]
        strongest_support = support_ranked[0]

        resistance_map = {
            row["strike"]: index + 1
            for index, row in enumerate(
                resistance_ranked
            )
        }

        support_map = {
            row["strike"]: index + 1
            for index, row in enumerate(
                support_ranked
            )
        }

        for row in rows:
            row["res_rank"] = resistance_map.get(
                row["strike"],
                0,
            )

            row["sup_rank"] = support_map.get(
                row["strike"],
                0,
            )

        pcr = (
            round(
                total_put_oi / total_call_oi,
                2,
            )
            if total_call_oi > 0
            else 0
        )

        support_resistance_gap = abs(
            strongest_resistance["strike"]
            - strongest_support["strike"]
        )

        put_call_oi_difference = (
            total_put_oi - total_call_oi
        )

        put_call_change_difference = (
            total_put_change
            - total_call_change
        )

        # Sideways logic
        close_levels = (
            support_resistance_gap
            <= STRIKE_STEP
        )

        total_oi_base = max(
            total_call_oi,
            total_put_oi,
            1,
        )

        balanced_oi = (
            abs(put_call_oi_difference)
            / total_oi_base
            < 0.18
        )

        balanced_change = (
            abs(put_call_change_difference)
            / max(
                abs(total_call_change),
                abs(total_put_change),
                1,
            )
            < 0.22
        )

        if close_levels and (
            balanced_oi or balanced_change
        ):
            signal = "🟡 SIDEWAYS / RANGE"

            message = (
                f"Support {strongest_support['strike']} અને "
                f"Resistance {strongest_resistance['strike']} નજીક છે. "
                "Call અને Put pressure બંને હોવાથી breakout પહેલાં WAIT."
            )

            signal_color = "#fff3cd"

        elif (
            total_put_change > total_call_change
            and total_put_oi > total_call_oi
        ):
            signal = "🟢 SUPPORT SIDE STRONG"

            message = (
                f"{strongest_support['strike']} support મજબૂત છે. "
                f"{strongest_resistance['strike']} ઉપર price sustain થાય "
                "પછી CALL side જુઓ."
            )

            signal_color = "#d9fbe6"

        elif (
            total_call_change > total_put_change
            and total_call_oi > total_put_oi
        ):
            signal = "🔴 RESISTANCE SIDE STRONG"

            message = (
                f"{strongest_resistance['strike']} resistance મજબૂત છે. "
                f"{strongest_support['strike']} નીચે price sustain થાય "
                "પછી PUT side જુઓ."
            )

            signal_color = "#ffe1e1"

        else:
            signal = "🟡 MIXED / WAIT"

            message = (
                "OI અને OI Change એક જ direction બતાવતા નથી. "
                "Option buying પહેલાં price breakout/breakdownની રાહ જુઓ."
            )

            signal_color = "#fff3cd"

        return jsonify({
            "nifty": round(nifty_price, 2),
            "atm": atm,
            "pcr": pcr,
            "expiry": selected_expiry,
            "time": datetime.now().strftime("%H:%M:%S"),

            "signal": signal,
            "message": message,
            "signal_color": signal_color,

            "rows": rows,

            "resistance": {
                "strike": strongest_resistance["strike"],
                "oi": strongest_resistance["call_oi"],
                "change": strongest_resistance["call_change"],
                "total": strongest_resistance["call_total"],
            },

            "support": {
                "strike": strongest_support["strike"],
                "oi": strongest_support["put_oi"],
                "change": strongest_support["put_change"],
                "total": strongest_support["put_total"],
            },

            "resistance_list": [
                {
                    "rank": index + 1,
                    "strike": row["strike"],
                    "oi": row["call_oi"],
                    "change": row["call_change"],
                    "total": row["call_total"],
                }
                for index, row in enumerate(
                    resistance_ranked
                )
            ],

            "support_list": [
                {
                    "rank": index + 1,
                    "strike": row["strike"],
                    "oi": row["put_oi"],
                    "change": row["put_change"],
                    "total": row["put_total"],
                }
                for index, row in enumerate(
                    support_ranked
                )
            ],

            "total_call_oi": fmt(total_call_oi),
            "total_put_oi": fmt(total_put_oi),

            "total_call_change": fmt(
                total_call_change
            ),

            "total_put_change": fmt(
                total_put_change
            ),

            "change_difference": fmt(
                put_call_change_difference
            ),
        })

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# HTML
# =========================================================

HTML = """
<!DOCTYPE html>
<html lang="gu">

<head>
<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width,initial-scale=1"
>

<title>NIFTY OI Dashboard</title>

<style>
*{
    box-sizing:border-box;
}

body{
    margin:0;
    padding:7px;
    background:#f3f5f8;
    font-family:Arial,sans-serif;
    color:#151515;
}

.card{
    background:#fff;
    border-radius:18px;
    padding:13px;
    margin:8px 2px;
    box-shadow:0 3px 9px rgba(0,0,0,.11);
}

.top-line{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:8px;
}

.nifty-label{
    font-size:18px;
    color:#555;
}

.nifty-price{
    font-size:29px;
    font-weight:900;
}

.top-grid{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:7px;
    margin-top:12px;
}

.top-box,
.summary-box{
    background:#f5f7f9;
    border-radius:13px;
    padding:9px 5px;
    text-align:center;
}

.label{
    color:#666;
    font-size:11px;
}

.value{
    margin-top:3px;
    font-weight:900;
    font-size:17px;
}

.signal{
    border-radius:17px;
    padding:14px 9px;
    margin:8px 2px;
    text-align:center;
    font-size:19px;
    font-weight:900;
    line-height:1.4;
}

.signal small{
    display:block;
    margin-top:5px;
    font-size:13px;
    font-weight:600;
}

h2{
    font-size:21px;
    margin:3px 0 12px;
}

.strike-row{
    display:grid;
    grid-template-columns:minmax(0,1fr) 74px minmax(0,1fr);
    gap:6px;
    border:1px solid #ddd;
    border-radius:14px;
    padding:6px;
    margin:7px 0;
}

.atm-row{
    background:#fff4c9;
    border:3px solid #dda800;
}

.side-box{
    border-radius:11px;
    text-align:center;
    padding:8px 4px;
}

.call-box{
    background:#fff0f0;
}

.put-box{
    background:#ebfaed;
}

.red{
    color:#df1d1d;
}

.green{
    color:#078524;
}

.blue{
    color:#0754c7;
}

.heading{
    font-size:13px;
    font-weight:900;
}

.data-value{
    font-size:16px;
    font-weight:900;
    margin-top:2px;
}

.change-value{
    font-size:15px;
    font-weight:900;
    margin-top:2px;
}

.total-value{
    font-size:14px;
    font-weight:900;
    margin-top:2px;
}

.center{
    border-radius:10px;
    background:#f0f2f4;
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    text-align:center;
    padding:5px 2px;
}

.strike-number{
    font-size:19px;
    font-weight:900;
}

.atm-text{
    color:#9e7000;
    font-size:11px;
    font-weight:900;
    margin-top:2px;
}

.badge{
    display:inline-block;
    margin-top:3px;
    padding:2px 5px;
    border-radius:6px;
    color:white;
    font-size:10px;
    font-weight:900;
}

.res-badge{
    background:#df2323;
}

.sup-badge{
    background:#148c34;
}

.level-grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:9px;
}

.level-box{
    border-radius:16px;
    padding:14px 7px;
    text-align:center;
}

.res-box{
    background:#ffe5e5;
    border:2px solid #e42626;
}

.sup-box{
    background:#e2f8e7;
    border:2px solid #139039;
}

.level-title{
    font-size:14px;
    font-weight:900;
}

.level-strike{
    font-size:30px;
    font-weight:900;
    margin-top:6px;
}

.level-total{
    font-size:19px;
    font-weight:900;
    margin-top:5px;
}

.level-detail{
    font-size:13px;
    font-weight:800;
    line-height:1.45;
    margin-top:5px;
}

.rank-grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:8px;
    margin-top:12px;
}

.rank-box{
    border-radius:13px;
    background:#f5f7f9;
    padding:9px 6px;
    text-align:center;
}

.rank-title{
    font-size:13px;
    font-weight:900;
    margin-bottom:6px;
}

.rank-row{
    padding:5px 0;
    border-bottom:1px solid #ddd;
    font-size:12px;
    font-weight:800;
    line-height:1.4;
}

.rank-row:last-child{
    border-bottom:none;
}

.summary-grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:7px;
}

.footer{
    text-align:center;
    font-size:11px;
    color:#777;
    padding:10px;
}

@media(max-width:390px){
    body{
        padding:4px;
    }

    .card{
        padding:10px;
    }

   
