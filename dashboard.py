from flask import Flask, jsonify, render_template_string
from datetime import datetime, date
import os
import time
import requests

app = Flask(__name__)

TOKEN = os.environ.get("UPSTOX_TOKEN", "").strip()

INDEX = "NSE_INDEX|Nifty 50"
CHAIN_URL = "https://api.upstox.com/v2/option/chain"
CONTRACT_URL = "https://api.upstox.com/v2/option/contract"
QUOTE_URL = "https://api.upstox.com/v2/market-quote/quotes"

STEP = 50
SIDE = 5
TIMEOUT = 18

EXPIRY_CACHE = {
    "value": None,
    "time": 0
}


def num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def fmt(value):
    value = num(value)

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


def money(value):
    value = num(value)

    if value <= 0:
        return "-"

    return f"₹{value:.2f}"


def headers():
    if not TOKEN:
        raise RuntimeError(
            "UPSTOX_TOKEN missing છે."
        )

    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }


def get_json(url, params):
    try:
        response = requests.get(
            url,
            headers=headers(),
            params=params,
            timeout=TIMEOUT
        )

    except requests.Timeout:
        raise RuntimeError(
            "Upstox API timeout."
        )

    except requests.RequestException as error:
        raise RuntimeError(
            f"Connection error: {error}"
        )

    try:
        payload = response.json()

    except ValueError:
        raise RuntimeError(
            f"Invalid response: HTTP {response.status_code}"
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


def oi_change(market):
    current = num(
        market.get("oi")
    )

    previous = num(
        market.get("prev_oi")
                or market.get("previous_oi")
        or market.get("close_oi")
        or 0
    )

    if previous:
        return current - previous

    for key in (
        "oi_day_change",
        "oi_change",
        "change_oi",
        "change_in_oi",
        "oi_change_value"
    ):
        value = market.get(key)

        if value not in (None, ""):
            return num(value)

    return 0.0


def active_expiry():
        now = time.time()

    if (
        EXPIRY_CACHE["value"]
        and now - EXPIRY_CACHE["time"] < 300
    ):
        return EXPIRY_CACHE["value"]

    payload = get_json(
        CONTRACT_URL,
        {
            "instrument_key": INDEX
        }
    )

    today = date.today().isoformat()

    expiries = sorted({
        str(item.get("expiry"))
        for item in payload.get("data", [])
        if item.get("expiry")
        and str(item.get("expiry")) >= today
    })

    if not expiries:
        raise RuntimeError(
            "Active NIFTY expiry મળી નથી."
        )

    EXPIRY_CACHE["value"] = expiries[0]
    EXPIRY_CACHE["time"] = now

    return expiries[0]


def fetch_chain():
    attempts = []

    try:
        attempts.append(
            active_expiry()
        )
    except Exception:
        pass

    attempts.extend([
        "current_week",
        "next_week",
        "current_month"
    ])

    checked = set()
    last_error = ""

    for expiry in attempts:
        if expiry in checked:
            continue

        checked.add(expiry)

        try:
            payload = get_json(
                CHAIN_URL,
                {
                    "instrument_key": INDEX,
                    "expiry_date": expiry
                }
            )

            chain = payload.get("data", [])

            if chain:
                actual_expiry = (
                    chain[0].get("expiry")
                    or expiry
                )

                EXPIRY_CACHE["value"] = actual_expiry
                EXPIRY_CACHE["time"] = time.time()

                return chain, actual_expiry

        except Exception as error:
            last_error = str(error)

    raise RuntimeError(
        last_error
        or "Active option-chain data મળ્યો નથી."
    )


def fetch_quotes(instrument_keys):
    if not instrument_keys:
        return {}

    payload = get_json(
        QUOTE_URL,
        {
            "instrument_key": ",".join(
                instrument_keys
            )
        }
    )

    quote_map = {}

    for response_key, quote in payload.get(
        "data",
        {}
    ).items():

        token = (
            quote.get("instrument_token")
            or response_key.replace(":", "|", 1)
        )

        quote_map[token] = quote

    return quote_map


# PART 3 PASTE BELOW THIS LINE
def option_side(option, quote_map):

    market = option.get(
        "market_data",
        {}
    )

    greeks = option.get(
        "option_greeks",
        {}
    )

    instrument_key = option.get(
        "instrument_key",
        ""
    )

    quote = quote_map.get(
        instrument_key,
        {}
    )

    oi = num(
        market.get("oi")
    )

    change = oi_change(
        market
    )

    total = oi + change

    ltp = num(
        quote.get("last_price")
        or market.get("ltp")
    )

    vwap = num(
        quote.get("average_price")
    )

    iv = num(
        greeks.get("iv")
    )

    if ltp > 0 and vwap > 0:

        if ltp > vwap:
            status = "VWAP ઉપર"
            status_class = "green"

        elif ltp < vwap:
            status = "VWAP નીચે"
            status_class = "red"

        else:
            status = "VWAP સરખું"
            status_class = "amber"

    else:

        status = "VWAP નથી"
        status_class = "amber"

    return {

        "oi_raw": oi,
        "change_raw": change,
        "total_raw": total,

        "oi": fmt(oi),
        "change": fmt(change),
        "total": fmt(total),

        "ltp": money(ltp),
        "vwap": money(vwap),

        "iv": (
            f"{iv:.2f}"
            if iv > 0
            else "-"
        ),

        "status": status,
        "status_class": status_class

    }


def make_row(
    item,
    atm,
    quote_map
):

    strike = int(
        num(
            item.get(
                "strike_price"
            )
        )
    )

    return {

        "strike": strike,

        "atm": strike == atm,

        "call": option_side(
            item.get(
                "call_options",
                {}
            ),
            quote_map
        ),

        "put": option_side(
            item.get(
                "put_options",
                {}
            ),
            quote_map
        )

    }


# PART 4 PASTE BELOW THIS LINE
@app.route("/api")
def api():

    try:

        chain, expiry = fetch_chain()

        nifty = next(
            (
                num(
                    item.get(
                        "underlying_spot_price"
                    )
                )
                for item in chain
                if num(
                    item.get(
                        "underlying_spot_price"
                    )
                ) > 0
            ),
            0
        )

        if nifty <= 0:
            raise RuntimeError(
                "NIFTY live price મળ્યો નથી."
            )

        atm = int(
            round(
                nifty / STEP
            ) * STEP
        )

        wanted = {
            atm
        }

        for count in range(
            1,
            SIDE + 1
        ):

            wanted.add(
                atm
                + count * STEP
            )

            wanted.add(
                atm
                - count * STEP
            )

        selected = []

        for item in chain:

            strike = int(
                num(
                    item.get(
                        "strike_price"
                    )
                )
            )

            if strike in wanted:
                selected.append(
                    item
                )

        instrument_keys = []

        for item in selected:

            call_key = (
                item
                .get(
                    "call_options",
                    {}
                )
                .get(
                    "instrument_key"
                )
            )

            put_key = (
                item
                .get(
                    "put_options",
                    {}
                )
                .get(
                    "instrument_key"
                )
            )

            if call_key:
                instrument_keys.append(
                    call_key
                )

            if put_key:
                instrument_keys.append(
                    put_key
                )

        quote_map = fetch_quotes(
            instrument_keys
        )

        strike_map = {}

        for item in selected:

            row = make_row(
                item,
                atm,
                quote_map
            )

            strike_map[
                row["strike"]
            ] = row

        if atm not in strike_map:

            raise RuntimeError(
                "ATM strike data મળ્યો નથી."
            )

        upper = []
        lower = []

        for count in range(
            1,
            SIDE + 1
        ):

            upper_strike = (
                atm
                + count * STEP
            )

            lower_strike = (
                atm
                - count * STEP
            )

            if upper_strike in strike_map:

                upper.append(
                    strike_map[
                        upper_strike
                    ]
                )

            if lower_strike in strike_map:

                lower.append(
                    strike_map[
                        lower_strike
                    ]
                )

        if not upper or not lower:

            raise RuntimeError(
                "ATM આસપાસના strikes મળ્યા નથી."
            )

        resistance = max(
            upper,
            key=lambda row:
            row["call"]["total_raw"]
        )

        support = max(
            lower,
            key=lambda row:
            row["put"]["total_raw"]
        )

        pairs = []

        for index in range(
            SIDE
        ):

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
                )

            })


# PART 5 PASTE BELOW THIS LINE
        return jsonify({

            "nifty": round(
                nifty,
                2
            ),

            "atm": atm,

            "expiry": expiry,

            "time": datetime.now().strftime(
                "%H:%M:%S"
            ),

            "atm_data": strike_map[
                atm
            ],

            "pairs": pairs,

            "resistance": {

                "strike": resistance[
                    "strike"
                ],

                "oi_raw": resistance[
                    "call"
                ][
                    "oi_raw"
                ],

                "change_raw": resistance[
                    "call"
                ][
                    "change_raw"
                ],

                "total_raw": resistance[
                    "call"
                ][
                    "total_raw"
                ],

                "oi": resistance[
                    "call"
                ][
                    "oi"
                ],

                "change": resistance[
                    "call"
                ][
                    "change"
                ],

                "total": resistance[
                    "call"
                ][
                    "total"
                ],

                "ltp": resistance[
                    "call"
                ][
                    "ltp"
                ],

                "vwap": resistance[
                    "call"
                ][
                    "vwap"
                ],

                "iv": resistance[
                    "call"
                ][
                    "iv"
                ],

                "status": resistance[
                    "call"
                ][
                    "status"
                ],

                "status_class": resistance[
                    "call"
                ][
                    "status_class"
                ]

            },

            "support": {

                "strike": support[
                    "strike"
                ],

                "oi_raw": support[
                    "put"
                ][
                    "oi_raw"
                ],

                "change_raw": support[
                    "put"
                ][
                    "change_raw"
                ],

                "total_raw": support[
                    "put"
                ][
                    "total_raw"
                ],

                "oi": support[
                    "put"
                ][
                    "oi"
                ],

                "change": support[
                    "put"
                ][
                    "change"
                ],

                "total": support[
                    "put"
                ][
                    "total"
                ],

                "ltp": support[
                    "put"
                ][
                    "ltp"
                ],

                "vwap": support[
                    "put"
                ][
                    "vwap"
                ],

                "iv": support[
                    "put"
                ][
                    "iv"
                ],

                "status": support[
                    "put"
                ][
                    "status"
                ],

                "status_class": support[
                    "put"
                ][
                    "status_class"
                ]

            }

        })

    except Exception as error:

        return jsonify({

            "error": str(
                error
            )

        }), 500


HTML = r"""
<!doctype html>

<html lang="gu">

<head>

<meta charset="utf-8">

<meta
    name="viewport"
    content="
        width=device-width,
        initial-scale=1
    "
>

<title>
    NIFTY OI Live
</title>

<style>

*{
    box-sizing:border-box;
}

body{
    margin:0;
    padding:4px;
    background:#f2f4f7;
    font-family:Arial,sans-serif;
    color:#151515;
}

.card{
    background:#ffffff;
    border-radius:14px;
    padding:9px;
    margin:7px 1px;
    box-shadow:0 2px 7px #cccccc;
}

.top{
    display:flex;
    justify-content:space-between;
    align-items:center;
}

.price{
    font-size:26px;
    font-weight:900;
}

.info,
.two,
.pair,
.levels,
.mini{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:5px;
}

.info{
    grid-template-columns:
        repeat(3,1fr);
    margin-top:8px;
}

.ibox{
    background:#f5f7f9;
    text-align:center;
    padding:6px 2px;
    border-radius:8px;
}

.label{
    font-size:9px;
    color:#666666;
}

.value{
    font-size:13px;
    font-weight:900;
}

.red{
    color:#d71919;
}

.green{
    color:#078524;
}

.amber{
    color:#9a7400;
}

.atm{
    background:#fff4c9;
    border:3px solid #d9a300;
}

.title{
    text-align:center;
    font-size:20px;
    font-weight:900;
    margin-bottom:6px;
}

.side,
.strike,
.level{
    border-radius:10px;
    padding:6px 3px;
    text-align:center;
}

.call,
.mcall{
    background:#fff0f0;
}

.put,
.mput{
    background:#eaf9ed;
}

.line{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:3px;
    font-size:10px;
    padding:2px 1px;
}

.total{
    margin-top:3px;
    padding:4px 1px;
    border-radius:6px;
    font-size:11px;
    font-weight:900;
}

.calltotal{
    background:#ffdada;
    color:#c60000;
}

.puttotal{
    background:#d7f4dd;
    color:#007b21;
}

.head{
    text-align:center;
    font-weight:900;
    padding:7px 2px;
    border-radius:8px;
    margin-bottom:5px;
    font-size:12px;
}

.reshead{
    background:#ffe1e1;
    color:#c60000;
}

.suphead{
    background:#def6e3;
    color:#007b21;
}

.pair{
    margin:5px 0;
}

.strike{
    background:#f8f9fa;
    border:1px solid #dddddd;
}

.resstrike{
    border-left:
        4px solid #db2424;
}

.supstrike{
    border-right:
        4px solid #148d35;
}

.strikenum{
    font-size:16px;
    font-weight:900;
    margin-bottom:4px;
}

.mini{
    gap:2px;
}

.mini > div{
    border-radius:6px;
    padding:4px 1px;
}

.small{
    font-size:8px;
}

.smallval{
    font-size:9px;
    font-weight:900;
}

.level{
    padding:10px 3px;
}

.reslevel{
    background:#ffe3e3;
    border:
        2px solid #db2424;
}

.suplevel{
    background:#e1f7e6;
    border:
        2px solid #148d35;
}

.levelstrike{
    font-size:24px;
    font-weight:900;
}

.leveldetail{
    font-size:11px;
    line-height:1.4;
}

.error{
    display:none;
    background:#ffe1e1;
    color:#a00000;
    text-align:center;
    font-weight:800;
}

</style>

</head>


# PART 6 PASTE BELOW THIS LINE
<body>

<div class="card">
    <div class="top">
        <span>NIFTY LIVE</span>
        <span class="price" id="nifty">Loading...</span>
    </div>

    <div class="info">
        <div class="ibox">
            <div class="label">ATM</div>
            <div class="value" id="atm">-</div>
        </div>

        <div class="ibox">
            <div class="label">Expiry</div>
            <div class="value" id="expiry">-</div>
        </div>

        <div class="ibox">
            <div class="label">Updated</div>
            <div class="value" id="updated">-</div>
        </div>
    </div>
</div>

<div class="card error" id="errorBox"></div>

<div class="card atm">
    <div class="title" id="atmTitle">
        ATM -
    </div>

    <div class="two" id="atmSides"></div>
</div>

<div class="card">
    <div class="two">
        <div class="head reshead">
            RESISTANCE SIDE
        </div>

        <div class="head suphead">
            SUPPORT SIDE
        </div>
    </div>

    <div id="pairs"></div>
</div>

<div class="card">
    <div class="levels">

        <div class="level reslevel">
            <b class="red">
                STRONG RESISTANCE
            </b>

            <div
                class="levelstrike red"
                id="resStrike"
            >
                -
            </div>

            <div
                class="leveldetail"
                id="resDetail"
            >
                -
            </div>
        </div>

        <div class="level suplevel">
            <b class="green">
                STRONG SUPPORT
            </b>

            <div
                class="levelstrike green"
                id="supStrike"
            >
                -
            </div>

            <div
                class="leveldetail"
                id="supDetail"
            >
                -
            </div>
        </div>

    </div>
</div>

<script>

const getElement = id =>
    document.getElementById(id);


function changeColor(value) {

    value = Number(
        value || 0
    );

    if (value > 0) {
        return "green";
    }

    if (value < 0) {
        return "red";
    }

    return "";
}


function optionBox(
    data,
    optionType,
    mini = false
) {

    const isCall =
        optionType === "CALL";

    const backgroundClass =
        isCall
        ? "mcall"
        : "mput";

    const sideClass =
        isCall
        ? "call"
        : "put";

    const colourClass =
        isCall
        ? "red"
        : "green";

    const wrapperClass =
        mini
        ? backgroundClass
        : "side " + sideClass;

    return `
        <div class="${wrapperClass}">

            <b class="${colourClass}">
                ${optionType}
            </b>

            <div class="line">
                <span>OI</span>

                <b class="${colourClass}">
                    ${data.oi}
                </b>
            </div>

            <div class="line">
                <span>OI Change</span>

                <b class="${
                    changeColor(
                        data.change_raw
                    )
                }">
                    ${data.change}
                </b>
            </div>

            <div class="line">
                <span>Live Price</span>

                <b>
                    ${data.ltp}
                </b>
            </div>

            <div class="line">
                <span>IV</span>

                <b>
                    ${data.iv}
                </b>
            </div>

            <div class="line">
                <span>VWAP</span>

                <b>
                    ${data.vwap}
                </b>
            </div>

            <div class="line">
                <span>Status</span>

                <b class="${
                    data.status_class
                }">
                    ${data.status}
                </b>
            </div>

            <div class="
                total
                ${
                    isCall
                    ? "calltotal"
                    : "puttotal"
                }
            ">
                Total ${data.total}
            </div>

        </div>
    `;
}


function strikeBox(
    row,
    sideClass
) {

    if (!row) {
        return `
            <div class="strike">
                Data નથી
            </div>
        `;
    }

    return `
        <div class="
            strike
            ${sideClass}
        ">

            <div class="strikenum">
                ${row.strike}
            </div>

            <div class="mini">

                ${
                    optionBox(
                        row.call,
                        "CALL",
                        true
                    )
                }

                ${
                    optionBox(
                        row.put,
                        "PUT",
                        true
                    )
                }

            </div>

        </div>
    `;
}


async function loadDashboard() {

    const errorBox =
        getElement(
            "errorBox"
        );

    try {

        const response =
            await fetch(
                "/api?t="
                + Date.now(),
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

        errorBox.style.display =
            "none";

        getElement(
            "nifty"
        ).innerText =
            data.nifty;

        getElement(
            "atm"
        ).innerText =
            data.atm;

        getElement(
            "expiry"
        ).innerText =
            data.expiry;

        getElement(
            "updated"
        ).innerText =
            data.time;

        getElement(
            "atmTitle"
        ).innerText =
            "ATM " + data.atm;

        getElement(
            "atmSides"
        ).innerHTML =

            optionBox(
                data.atm_data.call,
                "CALL"
            )

            +

            optionBox(
                data.atm_data.put,
                "PUT"
            );

        getElement(
            "pairs"
        ).innerHTML =

            data.pairs.map(
                pair => `
                    <div class="pair">

                        ${
                            strikeBox(
                                pair.upper,
                                "resstrike"
                            )
                        }

                        ${
                            strikeBox(
                                pair.lower,
                                "supstrike"
                            )
                        }

                    </div>
                `
            ).join("");

        const resistance =
            data.resistance;

        const support =
            data.support;

        getElement(
            "resStrike"
        ).innerText =
            resistance.strike;

        getElement(
            "resDetail"
        ).innerHTML =

            "Call OI "
            + resistance.oi

            + "<br>OI Change "
            + resistance.change

            + "<br>Live Price "
            + resistance.ltp

            + "<br>IV "
            + resistance.iv

            + "<br>VWAP "
            + resistance.vwap

            + "<br><b class='"
            + resistance.status_class
            + "'>"
            + resistance.status
            + "</b>"

            + "<br><b class='red'>"
            + "Total "
            + resistance.total
            + "</b>";

        getElement(
            "supStrike"
        ).innerText =
            support.strike;

        getElement(
            "supDetail"
        ).innerHTML =

            "Put OI "
            + support.oi

            + "<br>OI Change "
            + support.change

            + "<br>Live Price "
            + support.ltp

            + "<br>IV "
            + support.iv

            + "<br>VWAP "
            + support.vwap

            + "<br><b class='"
            + support.status_class
            + "'>"
            + support.status
            + "</b>"

            + "<br><b class='green'>"
            + "Total "
            + support.total
            + "</b>";

    } catch (error) {

        errorBox.style.display =
            "block";

        errorBox.innerText =
            error.message;
    }
}


loadDashboard();


setInterval(
    loadDashboard,
    3000
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


@app.route("/health")
def health():

    return jsonify({

        "status": "ok",

        "token_configured":
            bool(TOKEN)

    })


if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),

        debug=False

    )

    
