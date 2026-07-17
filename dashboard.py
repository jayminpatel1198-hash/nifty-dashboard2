from flask import Flask, jsonify, render_template_string
import os
from datetime import datetime

import requests

app = Flask(__name__)

# =========================================================
# CONFIGURATION
# =========================================================

UPSTOX_TOKEN = os.environ.get("UPSTOX_TOKEN", "").strip()

UNDERLYING = "NSE_INDEX|Nifty 50"
STRIKE_STEP = 50
STRIKES_EACH_SIDE = 5
REQUEST_TIMEOUT = 15


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def api_headers():
    if not UPSTOX_TOKEN:
        raise RuntimeError(
            "Render Environment માં UPSTOX_TOKEN add કરો"
        )

    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {UPSTOX_TOKEN}",
    }


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def format_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"

    sign = "+" if number > 0 else "-" if number < 0 else ""
    number = abs(number)

    if number >= 10_000_000:
        return f"{sign}{number / 10_000_000:.2f}Cr"

    if number >= 100_000:
        return f"{sign}{number / 100_000:.2f}L"

    if number >= 1_000:
        return f"{sign}{number / 1_000:.1f}K"

    return f"{sign}{number:.0f}"


def calculate_oi_change(market_data):
    """
    Current OI - Previous OI.

    Different API payload versions may use prev_oi,
    previous_oi or another change field, so fallbacks
    are included.
    """

    direct_change_keys = [
        "oi_day_change",
        "oi_change",
        "change_oi",
        "oi_change_value",
        "change_in_oi",
    ]

    for key in direct_change_keys:
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


def get_expiry_value():
    """
    Render Environment માં EXPIRY_DATE હોય તો તે વાપરે.
    ન હોય તો current_week expiry વાપરે.
    """

    expiry = os.environ.get("EXPIRY_DATE", "").strip()

    if expiry:
        return expiry

    return "current_week"


def fetch_option_chain():
    response = requests.get(
        "https://api.upstox.com/v2/option/chain",
        headers=api_headers(),
        params={
            "instrument_key": UNDERLYING,
            "expiry_date": get_expiry_value(),
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError(str(payload))

    data = payload.get("data", [])

    if not data:
        raise RuntimeError(
            "Option chain data મળ્યો નથી. "
            "EXPIRY_DATE સાચી છે કે નહીં તે check કરો."
        )

    return data


def ranking_text(rank):
    if rank == 1:
        return "સૌથી મજબૂત"
    if rank == 2:
        return "બીજા નંબરનું"
    if rank == 3:
        return "ત્રીજા નંબરનું"

    return ""


# =========================================================
# OPTION CHAIN API
# =========================================================

@app.route("/api")
def option_chain_api():
    try:
        chain = fetch_option_chain()

        nifty_price = 0.0
        expiry = get_expiry_value()

        for item in chain:
            spot = safe_float(item.get("underlying_spot_price"))

            if spot > 0:
                nifty_price = spot
                break

        if nifty_price <= 0:
            raise RuntimeError(
                "NIFTY live spot price મળ્યો નથી"
            )

        first_expiry = chain[0].get("expiry")

        if first_expiry:
            expiry = first_expiry

        atm = int(
            round(nifty_price / STRIKE_STEP) * STRIKE_STEP
        )

        lowest_strike = (
            atm - STRIKES_EACH_SIDE * STRIKE_STEP
        )

        highest_strike = (
            atm + STRIKES_EACH_SIDE * STRIKE_STEP
        )

        rows = []

        total_call_oi = 0.0
        total_put_oi = 0.0

        total_call_change = 0.0
        total_put_change = 0.0

        for item in chain:
            strike = int(
                safe_float(item.get("strike_price"))
            )

            if strike < lowest_strike:
                continue

            if strike > highest_strike:
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

            total_call_oi += call_oi
            total_put_oi += put_oi

            total_call_change += call_change
            total_put_change += put_change

            call_total = call_oi + call_change
            put_total = put_oi + put_change

            pressure_difference = put_total - call_total

            if pressure_difference > 0:
                row_class = "support-row"
                row_status = "SUPPORT"

            elif pressure_difference < 0:
                row_class = "resistance-row"
                row_status = "RESISTANCE"

            else:
                row_class = "balanced-row"
                row_status = "BALANCED"

            rows.append({
                "strike": strike,
                "is_atm": strike == atm,

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

                "row_class": row_class,
                "row_status": row_status,
            })

        rows.sort(
            key=lambda row: row["strike"]
        )

        if not rows:
            raise RuntimeError(
                "ATM ±5 strikes data મળ્યો નથી"
            )

        # Resistance ATM અથવા ATM ઉપર ગણીએ.
        resistance_candidates = [
            row
            for row in rows
            if row["strike"] >= atm
        ]

        # Support ATM અથવા ATM નીચે ગણીએ.
        support_candidates = [
            row
            for row in rows
            if row["strike"] <= atm
        ]

        if not resistance_candidates:
            resistance_candidates = rows

        if not support_candidates:
            support_candidates = rows

        # Call OI + positive Call change
        # દ્વારા resistance strength.
        resistance_ranked = sorted(
            resistance_candidates,
            key=lambda row: (
                row["call_total_raw"],
                row["call_oi_raw"],
            ),
            reverse=True,
        )[:3]

        # Put OI + positive Put change
        # દ્વારા support strength.
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

        resistance_rank_map = {
            row["strike"]: index + 1
            for index, row
            in enumerate(resistance_ranked)
        }

        support_rank_map = {
            row["strike"]: index + 1
            for index, row
            in enumerate(support_ranked)
        }

        for row in rows:
            resistance_rank = resistance_rank_map.get(
                row["strike"],
                0,
            )

            support_rank = support_rank_map.get(
                row["strike"],
                0,
            )

            row["resistance_rank"] = resistance_rank
            row["support_rank"] = support_rank

            row["resistance_badge"] = (
                f"R{resistance_rank}"
                if resistance_rank
                else ""
            )

            row["support_badge"] = (
                f"S{support_rank}"
                if support_rank
                else ""
            )

        pcr = (
            round(
                total_put_oi / total_call_oi,
                2,
            )
            if total_call_oi > 0
            else 0
        )

        change_difference = (
            total_put_change - total_call_change
        )

        oi_difference = (
            total_put_oi - total_call_oi
        )

        resistance_distance = (
            strongest_resistance["strike"]
            - nifty_price
        )

        support_distance = (
            nifty_price
            - strongest_support["strike"]
        )

        # =================================================
        # SIMPLE MARKET VIEW
        # =================================================

        bullish_points = 0
        bearish_points = 0

        market_reasons = []

        if total_put_change > total_call_change:
            bullish_points += 1

            market_reasons.append(
                "Put OI Change વધારે છે"
            )
        else:
            bearish_points += 1

            market_reasons.append(
                "Call OI Change વધારે છે"
            )

        if total_put_oi > total_call_oi:
            bullish_points += 1

            market_reasons.append(
                "Total Put OI વધારે છે"
            )
        else:
            bearish_points += 1

            market_reasons.append(
                "Total Call OI વધારે છે"
            )

        if pcr >= 1:
            bullish_points += 1

            market_reasons.append(
                "PCR 1 અથવા વધુ છે"
            )
        else:
            bearish_points += 1

            market_reasons.append(
                "PCR 1થી નીચે છે"
            )

        if (
            abs(
                strongest_resistance["strike"]
                - strongest_support["strike"]
            )
            <= STRIKE_STEP
        ):
            market_view = "🟡 SIDEWAYS / RANGE"

            market_message = (
                f"Support {strongest_support['strike']} "
                f"અને Resistance "
                f"{strongest_resistance['strike']} "
                "નજીક છે. Breakout કે breakdown "
                "થાય ત્યાં સુધી WAIT કરવું સારું."
            )

            market_color = "#fff3cd"

        elif bullish_points > bearish_points:
            market_view = "🟢 SUPPORT SIDE મજબૂત"

            market_message = (
                f"Support "
                f"{strongest_support['strike']} "
                "મજબૂત છે. ઉપર move માટે "
                f"{strongest_resistance['strike']} "
                "Resistance ઉપર price sustain થવું જોઈએ."
            )

            market_color = "#d9fbe6"

        elif bearish_points > bullish_points:
            market_view = "🔴 RESISTANCE SIDE મજબૂત"

            market_message = (
                f"Resistance "
                f"{strongest_resistance['strike']} "
                "મજબૂત છે. નીચે move માટે "
                f"{strongest_support['strike']} "
                "Support નીચે price sustain થવું જોઈએ."
            )

            market_color = "#ffe1e1"

        else:
            market_view = "🟡 બંને SIDE MIXED"

            market_message = (
                "Call અને Put pressure mixed છે. "
                "Option buying માટે WAIT કરવું સારું."
            )

            market_color = "#fff3cd"

        resistance_list = []

        for index, row in enumerate(
            resistance_ranked,
            start=1,
        ):
            resistance_list.append({
                "rank": index,
                "strength": ranking_text(index),
                "strike": row["strike"],

                "oi": row["call_oi"],
                "change": row["call_change"],
                "total": row["call_total"],

                "change_raw": row[
                    "call_change_raw"
                ],
            })

        support_list = []

        for index, row in enumerate(
            support_ranked,
            start=1,
        ):
            support_list.append({
                "rank": index,
                "strength": ranking_text(index),
                "strike": row["strike"],

                "oi": row["put_oi"],
                "change": row["put_change"],
                "total": row["put_total"],

                "change_raw": row[
                    "put_change_raw"
                ],
            })

        return jsonify({
            "nifty": round(nifty_price, 2),
            "atm": atm,
            "expiry": expiry,
            "pcr": pcr,

            "time": datetime.now().strftime(
                "%H:%M:%S"
            ),

            "rows": rows,

            "market_view": market_view,
            "market_message": market_message,
            "market_color": market_color,

            "market_reasons": market_reasons,

            "strongest_resistance": {
                "strike": strongest_resistance[
                    "strike"
                ],

                "oi": strongest_resistance[
                    "call_oi"
                ],

                "change": strongest_resistance[
                    "call_change"
                ],

                "total": strongest_resistance[
                    "call_total"
                ],

                "distance": round(
                    resistance_distance,
                    2,
                ),
            },

            "strongest_support": {
                "strike": strongest_support[
                    "strike"
                ],

                "oi": strongest_support[
                    "put_oi"
                ],

                "change": strongest_support[
                    "put_change"
                ],

                "total": strongest_support[
                    "put_total"
                ],

                "distance": round(
                    support_distance,
                    2,
                ),
            },

            "resistance_list": resistance_list,
            "support_list": support_list,

            "total_call_oi": format_number(
                total_call_oi
            ),

            "total_call_oi_raw": total_call_oi,

            "total_put_oi": format_number(
                total_put_oi
            ),

            "total_put_oi_raw": total_put_oi,

            "total_call_change": format_number(
                total_call_change
            ),

            "total_call_change_raw": (
                total_call_change
            ),

            "total_put_change": format_number(
                total_put_change
            ),

            "total_put_change_raw": (
                total_put_change
            ),

            "change_difference": format_number(
                change_difference
            ),

            "change_difference_raw": (
                change_difference
            ),

            "oi_difference": format_number(
                oi_difference
            ),

            "oi_difference_raw": oi_difference,
        })

    except requests.Timeout:
        return jsonify({
            "error": (
                "Upstox API timeout. "
                "થોડીવાર પછી refresh કરો."
            )
        }), 504

    except requests.RequestException as error:
        return jsonify({
            "error": f"Upstox API error: {error}"
        }), 502

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# HTML / CSS / JAVASCRIPT
# =========================================================

HTML = """
<!DOCTYPE html>

<html lang="gu">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="
            width=device-width,
            initial-scale=1,
            maximum-scale=1,
            user-scalable=no
        "
    >

    <title>NIFTY OI Dashboard</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 7px;

            background: #f3f5f8;

            font-family:
                Arial,
                sans-serif;

            color: #151515;
        }

        .card {
            background: white;

            border-radius: 17px;

            padding: 13px;

            margin: 8px 2px;

            box-shadow:
                0 3px 9px
                rgba(0, 0, 0, 0.11);
        }

        .top-card {
            padding: 15px;
        }

        .nifty-line {
            display: flex;

            align-items: center;
            justify-content: space-between;

            gap: 8px;
        }

        .nifty-label {
            font-size: 17px;
            color: #555;
        }

        .nifty-price {
            font-size: 29px;

            font-weight: 900;

            white-space: nowrap;
        }

        .top-info {
            display: grid;

            grid-template-columns:
                repeat(3, 1fr);

            gap: 6px;

            margin-top: 12px;
        }

        .top-box {
            background: #f6f7f9;

            border-radius: 12px;

            text-align: center;

            padding: 8px 4px;
        }

        .mini-label {
            font-size: 11px;
            color: #666;
        }

        .mini-value {
            margin-top: 3px;

            font-size: 16px;

            font-weight: 900;
        }

        .signal {
            border-radius: 16px;

            padding: 14px 10px;

            margin: 8px 2px;

            text-align: center;

            font-size: 18px;

            font-weight: 900;

            line-height: 1.4;
        }

        .signal-message {
            margin-top: 5px;

            font-size: 13px;

            font-weight: 600;
        }

        h2 {
            margin: 4px 0 12px;

            font-size: 21px;
        }

        .strike-list {
            display: flex;

            flex-direction: column;

            gap: 7px;
        }

        .strike-row {
            display: grid;

            grid-template-columns:
                minmax(0, 1fr)
                78px
                minmax(0, 1fr);

            gap: 6px;

            align-items: stretch;

            border:
                1px solid #e1e4e8;

            border-radius: 14px;

            padding: 6px;

            background: white;
        }

        .atm-row {
            border: 3px solid #e5ad00;

            background: #fff6d2;
        }

        .resistance-row {
            border-left:
                5px solid #e63b3b;
        }

        .support-row {
            border-right:
                5px solid #15933a;
        }

        .balanced-row {
            border-left:
                5px solid #e2b100;

            border-right:
                5px solid #e2b100;
        }

        .side-box {
            border-radius: 10px;

            padding: 8px 5px;

            text-align: center;

            background: #f7f8fa;

            min-width: 0;
        }

        .call-box {
            background: #fff0f0;
        }

        .put-box {
            background: #ecfbed;
        }

        .side-heading {
            font-size: 13px;

            font-weight: 900;
        }

        .oi-label {
            margin-top: 5px;

            font-size: 10px;

            color: #666;
        }

        .oi-value {
            margin-top: 2px;

            font-size: 17px;

            font-weight: 900;

            word-break: break-word;
        }

        .change-label {
            margin-top: 7px;

            font-size: 10px;

            color: #666;
        }

        .change-value {
            margin-top: 2px;

            font-size: 16px;

            font-weight: 900;

            word-break: break-word;
        }

        .total-label {
            margin-top: 7px;

            font-size: 10px;

            color: #666;
        }

        .total-value {
            margin-top: 2px;

            font-size: 14px;

            font-weight: 900;
        }

        .strike-center {
            border-radius: 10px;

            background: #f1f3f5;

            text-align: center;

            display: flex;

            flex-direction: column;

            justify-content: center;

            padding: 6px 2px;
        }

        .strike-number {
            font-size: 20px;

            font-weight: 900;
        }

        .atm-text {
            color: #9e6c00;

            font-size: 12px;

            font-weight: 900;

            margin-top: 3px;
        }

        .status-text {
            margin-top: 4px;

            color: #555;

            font-size: 9px;

            font-weight: 800;
        }

        .badges {
            margin-top: 4px;

            min-height: 18px;
        }

        .badge {
            display: inline-block;

            padding: 3px 5px;

            margin: 1px;

            border-radius: 7px;

            color: white;

            font-size: 10px;

            font-weight: 900;
        }

        .res-badge {
            background: #e12828;
        }

        .sup-badge {
            background: #128833;
        }

        .green {
            color: #078624;
        }

        .red {
            color: #e01d1d;
        }

        .blue {
            color: #0754c7;
        }

        .neutral {
            color: #444;
        }

        .levels-grid {
            display: grid;

            grid-template-columns:
                1fr 1fr;

            gap: 9px;
        }

        .level-box {
            border-radius: 15px;

            padding: 14px 7px;

            text-align: center;
        }

        .resistance-box {
            background: #ffe7e7;

            border:
                2px solid #e32c2c;
        }

        .support-box {
            background: #e3f9e8;

            border:
                2px solid #15933a;
        }

        .level-title {
            font-size: 14px;

            font-weight: 900;
        }

        .level-strike {
            margin-top: 6px;

            font-size: 31px;

            font-weight: 900;
        }

        .level-total {
            margin-top: 6px;

            font-size: 20px;

            font-weight: 900;
        }

        .level-detail {
            margin-top: 5px;

            font-size: 14px;

            font-weight: 800;

            line-height: 1.35;
        }

        .rank-section {
            margin-top: 13px;

            display: grid;

            grid-template-columns:
                1fr 1fr;

            gap: 8px;
        }

        .rank-box {
            background: #f7f8fa;

            padding: 9px 7px;

            border-radius: 12px;
        }

        .rank-title {
            text-align: center;

            font-size: 13px;

            font-weight: 900;

            margin-bottom: 7px;
        }

        .rank-line {
            padding: 6px 2px;

            border-bottom:
                1px solid #ddd;

            font-size: 13px;

            font-weight: 700;

            line-height: 1.4;
        }

        .rank-line:last-child {
            border-bottom: none;
        }

        .summary-grid {
            display: grid;

            grid-template-columns:
                1fr 1fr;

            gap: 7px;
        }

        .summary-box {
            background: #f6f7f9;

            border-radius: 12px;

            padding: 10px 5px;

            text-align: center;
        }

        .summary-label {
            font-size: 11px;

            color: #666;
        }

        .summary-value {
            margin-top: 4px;

            font-size: 18px;

            font-weight: 900;
        }

        .footer {
            text-align: center;

            color: #777;

            font-size: 11px;

            padding: 10px;
        }

        @media (max-width: 390px) {

            body {
                padding: 4px;
            }

            .card {
                padding: 10px;

                margin: 6px 1px;
            }

            .nifty-price {
                font-size: 26px;
            }

            .strike-row {
                grid-template-columns:
                    minmax(0, 1fr)
                    69px
                    minmax(0, 1fr);

                gap: 4px;

                padding: 5px;
            }

            .side-box {
                padding: 7px 3px;
            }

            .oi-value {
                font-size: 15px;
            }

            .change-value {
                font-size: 14px;
            }

            .total-value {
                font-size: 13px;
            }

            .strike-number {
                font-size: 17px;
            }

            .level-strike {
                font-size: 26px;
            }

            .level-total {
                font-size: 17px;
            }

            .level-detail {
                font-size: 12px;
            }

        }

    </style>

</head>

<body>

    <div class="card top-card">

        <div class="nifty-line">

            <span class="nifty-label">
                NIFTY LIVE
            </span>

            <span
                class="nifty-price"
                id="nifty"
            >
                Loading...
            </span>

        </div>

        <div class="top-info">

            <div class="top-box">

                <div class="mini-label">
                    ATM
                </div>

                <div
                    class="mini-value"
                    id="atm"
                >
                    -
                </div>

            </div>

            <div class="top-box">

                <div class="mini-label">
                    PCR
                </div>

                <div
                    class="mini-value"
                    id="pcr"
                >
                    -
                </div>

            </div>

            <div class="top-box">

                <div class="mini-label">
                    Updated
                </div>

                <div
                    class="mini-value"
                    id="updated"
                >
                    -
                </div>

            </div>

        </div>

    </div>

    <div
        class="signal"
        id="marketSignal"
    >
        Data loading...
    </div>

    <div class="card">

        <h2>
            ATM ±5 Strikes
        </h2>

        <div
            class="strike-list"
            id="strikeList"
        ></div>

    </div>

    <div class="card">

        <h2>
            Strong Resistance / Support
        </h2>

        <div class="levels-grid">

            <div
                class="
                    level-box
                    resistance-box
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
                    class="
                        level-total
                        red
                    "
                    id="resTotal"
                >
                    -
                </div>

                <div
                    class="level-detail"
                    id="resDetail"
                >
                    -
                </div>

            </div>

            <div
                class="
                    level-box
                    support-box
                "
            >

                <div
                    class="
                        level-title
                        green
                    "
                >
                    STRONG SUPPORT
                </div>

                <div
                    class="
                        level-strike
                        green
                    "
                    id="supStrike"
                >
                    -
                </div>

                <div
                    class="
                        level-total
                        green
                    "
                    id="supTotal"
                >
                    -
                </div>

                <div
                    class="level-detail"
                    id="supDetail"
                >
                    -
                </div>

            </div>

        </div>

        <div class="rank-section">

            <div class="rank-box">

                <div
                    class="
                        rank-title
                        red
                    "
                >
                    Resistance Ranking
                </div>

                <div
                    id="resistanceRanking"
                ></div>

            </div>

            <div class="rank-box">

                <div
                    class="
                        rank-title
                        green
                    "
                >
                    Support Ranking
                </div>

                <div
                    id="supportRanking"
                ></div>

            </div>

        </div>

    </div>

    <div class="card">

        <h2>
            Overall Summary
        </h2>

        <div class="summary-grid">

            <div class="summary-box">

                <div class="summary-label">
                    Total Call OI
                </div>

                <div
                    class="
                        summary-value
                        red
                    "
                    id="totalCallOi"
                >
                    -
                </div>

            </div>

            <div class="summary-box">

                <div class="summary-label">
                    Total Put OI
                </div>

                <div
                    class="
                        summary-value
                        green
                    "
                    id="totalPutOi"
                >
                    -
                </div>

            </div>

            <div class="summary-box">

                <div class="summary-label">
                    Call OI Change
                </div>

                <div
                    class="summary-value"
                    id="totalCallChange"
                >
                    -
                </div>

            </div>

            <div class="summary-box">

                <div class="summary-label">
                    Put OI Change
                </div>

                <div
                    class="summary-value"
                    id="totalPutChange"
                >
                    -
                </div>

            </div>

            <div class="summary-box">

                <div class="summary-label">
                    Put − Call Change
                </div>

                <div
                    class="summary-value"
                    id="changeDifference"
                >
                    -
                </div>

            </div>

            <div class="summary-box">

                <div class="summary-label">
                    Expiry
                </div>

                <div
                    class="summary-value"
                    id="expiry"
                >
                    -
                </div>

            </div>

        </div>

    </div>

    <div class="footer">
        Auto refresh every 3 seconds
    </div>

<script>

    function changeClass(value) {

        const number = Number(value || 0);

        if (number > 0) {
            return "green";
        }

        if (number < 0) {
            return "red";
        }

        return "neutral";

    }


    function makeStrikeRows(rows) {

        let html = "";

        rows.forEach(row => {

            const atmClass = (
                row.is_atm
                ? "atm-row"
                : ""
            );

            html += `
                <div
                    class="
                        strike-row
                        ${row.row_class}
                        ${atmClass}
                    "
                >

                    <div
                        class="
                            side-box
                            call-box
                        "
                    >

                        <div
                            class="
                                side-heading
                                red
                            "
                        >
                            CALL
                        </div>

                        <div class="oi-label">
                            OI
                        </div>

                        <div
                            class="
                                oi-value
                                red
                            "
                        >
                            ${row.call_oi}
                        </div>

                        <div class="change-label">
                            OI Change
                        </div>

                        <div
                            class="
                                change-value
                                ${changeClass(
                                    row.call_change_raw
                                )}
                            "
                        >
                            ${row.call_change}
                        </div>

                        <div class="total-label">
                            Total
                        </div>

                        <div
                            class="
                                total-value
                                red
                            "
                        >
                            ${row.call_total}
                        </div>

                    </div>

                    <div class="strike-center">

                        <div class="strike-number">
                            ${row.strike}
                        </div>

                        ${
                            row.is_atm
                            ? `
                                <div class="atm-text">
                                    ATM
                                </div>
                              `
                            : ""
                        }

                        <div class="badges">

                            ${
                                row.resistance_badge
                                ? `
                                    <span
                                        class="
                                            badge
                                            res-badge
                                        "
                                    >
                                        ${row.resistance_badge}
                                    </span>
                                  `
                                : ""
                            }

                            ${
                                row.support_badge
                                ? `
                                    <span
                                        class="
                                            badge
                                            sup-badge
                                        "
                                    >
                                        ${row.support_badge}
                                    </span>
                                  `
                                : ""
                            }

                        </div>

                        <div class="status-text">
                            ${row.row_status}
                        </div>

                    </div>

                    <div
                        class="
                            side-box
                            put-box
                        "
                    >

                        <div
                            class="
                                side-heading
                                green
                            "
                        >
                            PUT
                        </div>

                        <div class="oi-label">
                            OI
                        </div>

                        <div
                            class="
                                oi-value
                                green
                            "
                        >
                            ${row.put_oi}
                        </div>

                        <div class="change-label">
                            OI Change
                        </div>

                        <div
                            class="
                                change-value
                                ${changeClass(
                                    row.put_change_raw
                                )}
                            "
                        >
                            ${row.put_change}
                        </div>

                        <div class="total-label">
                            Total
                        </div>

                        <div
                            class="
                                total-value
                                green
                            "
                        >
                            ${row.put_total}
                        </div>

                    </div>

                </div>
            `;

        });

        return html;

    }


    function makeRanking(
        items,
        sideClass
    ) {

        return items.map(item => `
            <div
                class="
                    rank-line
                    ${sideClass}
                "
            >
                ${item.rank})
                ${item.strike}

                <br>

                OI ${item.oi}

                <br>

                Change ${item.change}

                <br>

                Total ${item.total}
            </div>
        `).join("");

    }


    async function loadData() {

        const marketSignal =
            document.getElementById(
                "marketSignal"
            );

        try {

            const response = await fetch(
                `/api?t=${Date.now()}`,
                {
                    cache: "no-store"
                }
            );

            const data =
                await response.json();

            if (
                !response.ok
                || data.error
            ) {
                throw new Error(
                    data.error
                    || "Data load failed"
                );
            }

            document.getElementById(
                "nifty"
            ).innerText = data.nifty;

            document.getElementById(
                "atm"
            ).innerText = data.atm;

            document.getElementById(
                "pcr"
            ).innerText = data.pcr;

            document.getElementById(
                "updated"
            ).innerText = data.time;

            document.getElementById(
                "expiry"
            ).innerText = data.expiry;

            marketSignal.innerHTML = `
                ${data.market_view}

                <div class="signal-message">
                    ${data.market_message}
                </div>
            `;

            marketSignal.style.background =
                data.market_color;

            document.getElementById(
                "strikeList"
            ).innerHTML = makeStrikeRows(
                data.rows
            );

            document.getElementById(
                "resStrike"
            ).innerText =
                data
                .strongest_resistance
                .strike;

            document.getElementById(
                "resTotal"
            ).innerText =
                `Total ${
                    data
                    .strongest_resistance
                    .total
                }`;

            document.getElementById(
                "resDetail"
            ).innerHTML = `
                Call OI
                ${
                    data
                    .strongest_resistance
                    .oi
                }

                <br>

                Change
                ${
                    data
                    .strongest_resistance
                    .change
                }
            `;

            document.getElementById(
                "supStrike"
            ).innerText =
                data
                .strongest_support
                .strike;

            document.getElementById(
                "supTotal"
            ).innerText =
                `Total ${
                    data
                    .strongest_support
                    .total
                }`;

            document.getElementById(
                "supDetail"
            ).innerHTML = `
                Put OI
                ${
                    data
                    .strongest_support
                    .oi
                }

                <br>

                Change
                ${
                    data
                    .strongest_support
                    .change
                }
            `;

            document.getElementById(
                "resistanceRanking"
            ).innerHTML = makeRanking(
                data.resistance_list,
                "red"
            );

            document.getElementById(
                "supportRanking"
            ).innerHTML = makeRanking(
                data.support_list,
                "green"
            );

            document.getElementById(
                "totalCallOi"
            ).innerText =
                data.total_call_oi;

            document.getElementById(
                "totalPutOi"
            ).innerText =
                data.total_put_oi;

            const callChange =
                document.getElementById(
                    "totalCallChange"
                );

            callChange.innerText =
                data.total_call_change;

            callChange.className = `
                summary-value
                ${changeClass(
                    data.total_call_change_raw
                )}
            `;

            const putChange =
                document.getElementById(
                    "totalPutChange"
                );

            putChange.innerText =
                data.total_put_change;

            putChange.className = `
                summary-value
                ${changeClass(
                    data.total_put_change_raw
                )}
            `;

            const changeDiff =
                document.getElementById(
                    "changeDifference"
                );

            changeDiff.innerText =
                data.change_difference;

            changeDiff.className = `
                summary-value
                ${changeClass(
                    data.change_difference_raw
                )}
            `;

        } catch (error) {

            marketSignal.innerText =
                error.message;

            marketSignal.style.background =
                "#ffe1e1";

        }

    }


    loadData();

    setInterval(
        loadData,
        3000
    );

</script>

</body>

</html>
"""


# =========================================================
# HOME ROUTE
# =========================================================

@app.route("/")
def home():
    return render_template_string(HTML)


# =========================================================
# LOCAL / RENDER START
# =========================================================

if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            5000,
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )
