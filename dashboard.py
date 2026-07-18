from flask import Flask, jsonify, render_template_string
from datetime import datetime, date
import os
import requests

app = Flask(__name__)

TOKEN = os.environ.get("UPSTOX_TOKEN", "").strip()

UNDERLYING = "NSE_INDEX|Nifty 50"
STRIKE_STEP = 50
SIDE_STRIKES = 5
TIMEOUT = 18

CHAIN_URL = "https://api.upstox.com/v2/option/chain"
CONTRACT_URL = "https://api.upstox.com/v2/option/contract"


# =========================================================
# HELPERS
# =========================================================

def api_headers():
    if not TOKEN:
        raise RuntimeError(
            "UPSTOX_TOKEN missing છે. Render Environment માં token add કરો."
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


def format_number(value):
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


def get_oi_change(market_data):
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

    current_oi = safe_float(
        market_data.get("oi")
    )

    previous_oi = safe_float(
        market_data.get("prev_oi")
        or market_data.get("previous_oi")
        or market_data.get("close_oi")
        or 0
    )

    if previous_oi:
        return current_oi - previous_oi

    return 0.0


def request_json(url, params):
    try:
        response = requests.get(
            url,
            headers=api_headers(),
            params=params,
            timeout=TIMEOUT,
        )

    except requests.Timeout:
        raise RuntimeError(
            "Upstox API timeout. ફરી refresh કરો."
        )

    except requests.RequestException as error:
        raise RuntimeError(
            f"Upstox connection error: {error}"
        )

    try:
        payload = response.json()

    except ValueError:
        raise RuntimeError(
            f"Upstox invalid response. HTTP {response.status_code}"
        )

    if response.status_code == 401:
        raise RuntimeError(
            "UPSTOX_TOKEN invalid અથવા expired છે."
        )

    if not response.ok:
        raise RuntimeError(
            payload.get("message")
            or f"Upstox HTTP {response.status_code}"
        )

    if payload.get("status") != "success":
        raise RuntimeError(
            payload.get("message")
            or str(payload)
        )

    return payload


# =========================================================
# EXPIRY + OPTION CHAIN
# =========================================================

def get_active_expiries():
    try:
        payload = request_json(
            CONTRACT_URL,
            {
                "instrument_key": UNDERLYING
            },
        )

        today_text = date.today().isoformat()

        expiries = sorted({
            str(item.get("expiry"))
            for item in payload.get("data", [])
            if item.get("expiry")
            and str(item.get("expiry")) >= today_text
        })

        return expiries

    except Exception:
        return []


def fetch_option_chain():
    expiry_attempts = ["current_week"]

    expiry_attempts.extend(
        get_active_expiries()[:8]
    )

    expiry_attempts.extend([
        "next_week",
        "current_month",
    ])

    already_checked = set()
    last_error = None

    for expiry_value in expiry_attempts:
        if expiry_value in already_checked:
            continue

        already_checked.add(expiry_value)

        try:
            payload = request_json(
                CHAIN_URL,
                {
                    "instrument_key": UNDERLYING,
                    "expiry_date": expiry_value,
                },
            )

            data = payload.get("data", [])

            if data:
                actual_expiry = (
                    data[0].get("expiry")
                    or expiry_value
                )

                return data, actual_expiry

        except Exception as error:
            last_error = str(error)

    raise RuntimeError(
        last_error
        or "Active NIFTY Option Chain data મળ્યો નથી."
    )


# =========================================================
# PREPARE ONE STRIKE
# =========================================================

def make_strike_row(item, atm):
    strike = int(
        safe_float(
            item.get("strike_price")
        )
    )

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

    call_change = get_oi_change(
        call_market
    )

    put_change = get_oi_change(
        put_market
    )

    # User requested Total:
    # Total = Current OI + OI Change
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

        "call_oi": format_number(call_oi),
        "call_change": format_number(call_change),
        "call_total": format_number(call_total),

        "put_oi": format_number(put_oi),
        "put_change": format_number(put_change),
        "put_total": format_number(put_total),
    }


# =========================================================
# API
# =========================================================

@app.route("/api")
def dashboard_api():
    try:
        chain, expiry = fetch_option_chain()

        nifty_price = 0.0

        for item in chain:
            spot = safe_float(
                item.get("underlying_spot_price")
            )

            if spot > 0:
                nifty_price = spot
                break

        if nifty_price <= 0:
            raise RuntimeError(
                "NIFTY live price મળ્યો નથી."
            )

        # NIFTY બદલાય ત્યારે ATM auto બદલાશે
        atm = int(
            round(nifty_price / STRIKE_STEP)
            * STRIKE_STEP
        )

        required_strikes = {
            atm
        }

        for number in range(
            1,
            SIDE_STRIKES + 1,
        ):
            required_strikes.add(
                atm + number * STRIKE_STEP
            )

            required_strikes.add(
                atm - number * STRIKE_STEP
            )

        strike_map = {}

        for item in chain:
            strike = int(
                safe_float(
                    item.get("strike_price")
                )
            )

            if strike in required_strikes:
                strike_map[strike] = make_strike_row(
                    item,
                    atm,
                )

        if atm not in strike_map:
            raise RuntimeError(
                "ATM strike data મળ્યો નથી."
            )

        atm_data = strike_map[atm]

        resistance_side = []
        support_side = []

        for number in range(
            1,
            SIDE_STRIKES + 1,
        ):
            resistance_strike = (
                atm + number * STRIKE_STEP
            )

            support_strike = (
                atm - number * STRIKE_STEP
            )

            if resistance_strike in strike_map:
                resistance_side.append(
                    strike_map[resistance_strike]
                )

            if support_strike in strike_map:
                support_side.append(
                    strike_map[support_strike]
                )

        if not resistance_side:
            raise RuntimeError(
                "ATM ઉપરના strikes મળ્યા નથી."
            )

        if not support_side:
            raise RuntimeError(
                "ATM નીચેના strikes મળ્યા નથી."
            )

        strongest_resistance = max(
            resistance_side,
            key=lambda row: row[
                "call_total_raw"
            ],
        )

        strongest_support = max(
            support_side,
            key=lambda row: row[
                "put_total_raw"
            ],
        )

        paired_rows = []

        maximum_rows = max(
            len(resistance_side),
            len(support_side),
        )

        for index in range(maximum_rows):
            paired_rows.append({
                "resistance": (
                    resistance_side[index]
                    if index < len(resistance_side)
                    else None
                ),

                "support": (
                    support_side[index]
                    if index < len(support_side)
                    else None
                ),
            })

        return jsonify({
            "nifty": round(
                nifty_price,
                2,
            ),

            "atm": atm,
            "expiry": expiry,

            "time": datetime.now().strftime(
                "%H:%M:%S"
            ),

            "atm_data": atm_data,
            "paired_rows": paired_rows,

            "strongest_resistance": {
                "strike": strongest_resistance[
                    "strike"
                ],

                "call_oi": strongest_resistance[
                    "call_oi"
                ],

                "call_change": strongest_resistance[
                    "call_change"
                ],

                "call_total": strongest_resistance[
                    "call_total"
                ],
            },

            "strongest_support": {
                "strike": strongest_support[
                    "strike"
                ],

                "put_oi": strongest_support[
                    "put_oi"
                ],

                "put_change": strongest_support[
                    "put_change"
                ],

                "put_total": strongest_support[
                    "put_total"
                ],
            },
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

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    padding: 6px;
    background: #f2f4f7;
    font-family: Arial, sans-serif;
    color: #151515;
}

.card {
    background: white;
    border-radius: 16px;
    padding: 11px;
    margin: 7px 1px;
    box-shadow: 0 2px 8px rgba(0,0,0,.12);
}

.top-line {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.top-label {
    color: #555;
    font-size: 16px;
}

.nifty-price {
    font-size: 28px;
    font-weight: 900;
}

.top-info {
    display: grid;
    grid-template-columns: repeat(3,1fr);
    gap: 6px;
    margin-top: 10px;
}

.info-box {
    background: #f5f7f9;
    border-radius: 11px;
    padding: 8px 3px;
    text-align: center;
}

.small-label {
    color: #666;
    font-size: 10px;
}

.info-value {
    margin-top: 2px;
    font-size: 15px;
    font-weight: 900;
}

h2 {
    margin: 2px 0 10px;
    font-size: 19px;
}

.red {
    color: #df1d1d;
}

.green {
    color: #078524;
}

.blue {
    color: #0754c7;
}

.atm-card {
    border: 3px solid #d9a300;
    background: #fff4c9;
}

.atm-title {
    text-align: center;
    font-size: 22px;
    font-weight: 900;
    margin-bottom: 8px;
}

.atm-data-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 7px;
}

.data-side {
    border-radius: 12px;
    padding: 9px 5px;
    text-align: center;
}

.call-side {
    background: #fff0f0;
}

.put-side {
    background: #eaf9ed;
}

.side-title {
    font-size: 15px;
    font-weight: 900;
    margin-bottom: 7px;
}

.data-line {
    display: flex;
    justify-content: space-between;
    gap: 4px;
    padding: 4px 2px;
    border-bottom: 1px solid rgba(0,0,0,.08);
    font-size: 12px;
}

.data-line:last-child {
    border-bottom: none;
}

.data-name {
    color: #555;
}

.data-number {
    font-weight: 900;
}

.total-line {
    margin-top: 5px;
    padding: 7px 3px;
    border-radius: 9px;
    font-size: 15px;
    font-weight: 900;
}

.call-total {
    background: #ffdcdc;
    color: #c90000;
}

.put-total {
    background: #d8f5de;
    color: #007d22;
}

.headings {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 7px;
    margin-bottom: 6px;
}

.heading-box {
    padding: 9px 4px;
    text-align: center;
    border-radius: 11px;
    font-size: 14px;
    font-weight: 900;
}

.res-heading {
    color: #c90000;
    background: #ffe1e1;
}

.sup-heading {
    color: #007d22;
    background: #def6e3;
}

.pair-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 7px;
    margin: 7px 0;
}

.strike-box {
    background: #f7f8fa;
    border-radius: 13px;
    padding: 8px 5px;
    border: 1px solid #ddd;
}

.resistance-strike {
    border-left: 4px solid #df2626;
}

.support-strike {
    border-right: 4px solid #158e36;
}

.strike-number {
    text-align: center;
    font-size: 19px;
    font-weight: 900;
    margin-bottom: 6px;
}

.mini-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 5px;
}

.mini-side {
    border-radius: 9px;
    padding: 6px 3px;
    text-align: center;
}

.mini-call {
    background: #fff0f0;
}

.mini-put {
    background: #eaf9ed;
}

.mini-title {
    font-size: 11px;
    font-weight: 900;
}

.mini-label {
    color: #666;
    font-size: 9px;
    margin-top: 4px;
}

.mini-value {
    font-size: 12px;
    font-weight: 900;
    margin-top: 1px;
}

.mini-total {
    margin-top: 5px;
    padding: 5px 2px;
    border-radius: 7px;
    font-size: 12px;
    font-weight: 900;
}

.level-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.level-box {
    border-radius: 14px;
    padding: 13px 5px;
    text-align: center;
}

.res-level {
    background: #ffe3e3;
    border: 2px solid #dc2525;
}

.sup-level {
    background: #e1f7e6;
    border: 2px solid #148e36;
}

.level-title {
    font-size: 13px;
    font-weight: 900;
}

.level-strike {
    margin-top: 5px;
    font-size: 27px;
    font-weight: 900;
}

.level-detail {
    margin-top: 5px;
    font-size: 13px;
    font-weight: 800;
    line-height: 1.45;
}

.error-box {
    display: none;
    background: #ffe1e1;
    color: #a60000;
    font-weight: 800;
    text-align: center;
}

.footer {
    padding: 9px;
    text-align: center;
    color: #777;
    font-size: 11px;
}

@media(max-width:390px) {

    body {
        padding: 4px;
    }

    .card {
        padding: 9px;
    }

    .nifty-price {
        font-size: 25px;
    }

    .pair-row {
        gap: 5px;
    }

    .strike-box {
        padding: 7px 3px;
    }

    .mini-grid {
        gap: 3px;
    }

    .mini-value {
        font-size: 11px;
    }

    .mini-total {
        font-size: 11px;
    }

    .strike-number {
        font-size: 17px;
    }

}

</style>

</head>

<body>

<div class="card">

    <div class="top-line">

        <div class="top-label">
            NIFTY LIVE
        </div>

        <div
            class="nifty-price"
            id="nifty"
        >
            Loading...
        </div>

    </div>

    <div class="top-info">

        <div class="info-box">

            <div class="small-label">
                ATM
            </div>

            <div
                class="info-value"
                id="atm"
            >
                -
            </div>

        </div>

        <div class="info-box">

            <div class="small-label">
                Expiry
            </div>

            <div
                class="info-value"
                id="expiry"
            >
                -
            </div>

        </div>

        <div class="info-box">

            <div class="small-label">
                Updated
            </div>

            <div
                class="info-value"
                id="updated"
            >
                -
            </div>

        </div>

    </div>

</div>

<div
    class="card error-box"
    id="errorBox"
></div>

<div class="card atm-card">

    <div
        class="atm-title"
        id="atmTitle"
    >
        ATM -
    </div>

    <div class="atm-data-grid">

        <div class="data-side call-side">

            <div class="side-title red">
                ATM CALL
            </div>

            <div class="data-line">

                <span class="data-name">
                    Call OI
                </span>

                <span
                    class="data-number red"
                    id="atmCallOi"
                >
                    -
                </span>

            </div>

            <div class="data-line">

                <span class="data-name">
                    Call Change
                </span>

                <span
                    class="data-number"
                    id="atmCallChange"
                >
                    -
                </span>

            </div>

            <div
                class="total-line call-total"
                id="atmCallTotal"
            >
                Total -
            </div>

        </div>

        <div class="data-side put-side">

            <div class="side-title green">
                ATM PUT
            </div>

            <div class="data-line">

                <span class="data-name">
                    Put OI
                </span>

                <span
                    class="data-number green"
                    id="atmPutOi"
                >
                    -
                </span>

            </div>

            <div class="data-line">

                <span class="data-name">
                    Put Change
                </span>

                <span
                    class="data-number"
                    id="atmPutChange"
                >
                    -
                </span>

            </div>

            <div
                class="total-line put-total"
                id="atmPutTotal"
            >
                Total -
            </div>

        </div>

    </div>

</div>

<div class="card">

    <div class="headings">

        <div class="heading-box res-heading">
            RESISTANCE SIDE
        </div>

        <div class="heading-box sup-heading">
            SUPPORT SIDE
        </div>

    </div>

    <div id="pairedRows"></div>

</div>

<div class="card">

    <h2>
        Strong Resistance / Support
    </h2>

    <div class="level-grid">

        <div
            class="
                level-box
                res-level
            "
        >

            <div
                class="
                    level-title
                    red
                "
            >
                STRONG RESISTANCE
            </div>

            <div
                class="
                    level-strike
                    red
                "
                id="resStrike"
            >
                -
            </div>

            <div
                class="level-det
