from flask import Flask, jsonify, render_template_string
from datetime import datetime, date
import os, requests

app = Flask(__name__)

TOKEN = os.environ.get("UPSTOX_TOKEN", "").strip()
INDEX = "NSE_INDEX|Nifty 50"
CHAIN = "https://api.upstox.com/v2/option/chain"
CONTRACT = "https://api.upstox.com/v2/option/contract"
STEP, SIDE, TIMEOUT = 50, 5, 15


def n(v):
    try:
        return float(v or 0)
    except:
        return 0.0


def fmt(v):
    v = n(v)
    if abs(v) < 0.5:
        return "0"
    s = "+" if v > 0 else "-"
    v = abs(v)
    if v >= 10000000:
        return f"{s}{v/10000000:.2f}Cr"
    if v >= 100000:
        return f"{s}{v/100000:.2f}L"
    if v >= 1000:
        return f"{s}{v/1000:.1f}K"
    return f"{s}{v:.0f}"


def hdr():
    if not TOKEN:
        raise RuntimeError("UPSTOX_TOKEN missing છે.")
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }


def get_json(url, params):
    try:
        r = requests.get(
            url,
            headers=hdr(),
            params=params,
            timeout=TIMEOUT
        )
    except requests.Timeout:
        raise RuntimeError("Upstox API timeout.")
    except requests.RequestException as e:
        raise RuntimeError(f"Connection error: {e}")

    try:
        data = r.json()
    except:
        raise RuntimeError(f"Invalid Upstox response: HTTP {r.status_code}")

    if r.status_code == 401:
        raise RuntimeError("UPSTOX_TOKEN invalid અથવા expired છે.")

    if not r.ok:
        msg = data.get("message") if isinstance(data, dict) else ""
        raise RuntimeError(msg or f"Upstox HTTP {r.status_code}")

    if data.get("status") != "success":
        raise RuntimeError(data.get("message") or str(data))

    return data


def oi_change(md):
    for key in (
        "oi_day_change",
        "oi_change",
        "change_oi",
        "change_in_oi",
        "oi_change_value"
    ):
        if md.get(key) not in (None, ""):
            return n(md.get(key))

    oi = n(md.get("oi"))
    prev = n(
        md.get("prev_oi")
        or md.get("previous_oi")
        or md.get("close_oi")
        or 0
    )
    return oi - prev if prev else 0.0


def expiries():
    try:
        d = get_json(CONTRACT, {"instrument_key": INDEX})
        today = date.today().isoformat()
        return sorted({
            str(x.get("expiry"))
            for x in d.get("data", [])
            if x.get("expiry")
            and str(x.get("expiry")) >= today
        })
    except:
        return []


def fetch_chain():
    tries = expiries()[:8] + [
        "current_week",
        "next_week",
        "far_week",
        "current_month"
    ]

    seen, last = set(), ""

    for exp in tries:
        if exp in seen:
            continue
        seen.add(exp)

        try:
            d = get_json(
                CHAIN,
                {
                    "instrument_key": INDEX,
                    "expiry_date": exp
                }
            )
            rows = d.get("data", [])
            if rows:
                actual = rows[0].get("expiry") or exp
                return rows, actual
        except Exception as e:
            last = str(e)

    raise RuntimeError(last or "Active option-chain data મળ્યો નથી.")


def make_row(item, atm):
    strike = int(n(item.get("strike_price")))

    cm = item.get("call_options", {}).get("market_data", {})
    pm = item.get("put_options", {}).get("market_data", {})

    coi, poi = n(cm.get("oi")), n(pm.get("oi"))
    cchg, pchg = oi_change(cm), oi_change(pm)

    # User-requested Total:
    ctotal = coi + cchg
    ptotal = poi + pchg

    return {
        "strike": strike,
        "atm": strike == atm,

        "coi_raw": coi,
        "cchg_raw": cchg,
        "ctotal_raw": ctotal,

        "poi_raw": poi,
        "pchg_raw": pchg,
        "ptotal_raw": ptotal,

        "coi": fmt(coi),
        "cchg": fmt(cchg),
        "ctotal": fmt(ctotal),

        "poi": fmt(poi),
        "pchg": fmt(pchg),
        "ptotal": fmt(ptotal)
    }


@app.route("/api")
def api():
    try:
        chain, expiry = fetch_chain()

        nifty = next(
            (
                n(x.get("underlying_spot_price"))
                for x in chain
                if n(x.get("underlying_spot_price")) > 0
            ),
            0
        )

        if nifty <= 0:
            raise RuntimeError("NIFTY live price મળ્યો નથી.")

        atm = int(round(nifty / STEP) * STEP)

        wanted = {atm}
        for i in range(1, SIDE + 1):
            wanted.add(atm + i * STEP)
            wanted.add(atm - i * STEP)

        strike_map = {}

        for item in chain:
            strike = int(n(item.get("strike_price")))
            if strike in wanted:
                strike_map[strike] = make_row(item, atm)

        if atm not in strike_map:
            raise RuntimeError("ATM strike data મળ્યો નથી.")

        upper, lower = [], []

        for i in range(1, SIDE + 1):
            up = atm + i * STEP
            down = atm - i * STEP

            if up in strike_map:
                upper.append(strike_map[up])

            if down in strike_map:
                lower.append(strike_map[down])

        if not upper or not lower:
            raise RuntimeError("ATM આસપાસના strikes મળ્યા નથી.")

        resistance = max(upper, key=lambda x: x["ctotal_raw"])
        support = max(lower, key=lambda x: x["ptotal_raw"])

        pairs = []

        for i in range(SIDE):
            pairs.append({
                "upper": upper[i] if i < len(upper) else None,
                "lower": lower[i] if i < len(lower) else None
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
                "oi": resistance["coi"],
                "change": resistance["cchg"],
                "total": resistance["ctotal"]
            },

            "support": {
                "strike": support["strike"],
                "oi": support["poi"],
                "change": support["pchg"],
                "total": support["ptotal"]
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


HTML = r"""
<!doctype html>
<html lang="gu">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NIFTY OI</title>
<style>
*{box-sizing:border-box}
body{margin:0;padding:5px;background:#f2f4f7;font-family:Arial;color:#151515}
.card{background:#fff;border-radius:14px;padding:9px;margin:7px 1px;box-shadow:0 2px 7px #ccc}
.top{display:flex;justify-content:space-between;align-items:center}
.price{font-size:27px;font-weight:900}
.info,.two,.pair,.levels{display:grid;grid-template-columns:1fr 1fr;gap:5px}
.info{grid-template-columns:repeat(3,1fr);margin-top:9px}
.ibox{background:#f5f7f9;text-align:center;padding:7px 2px;border-radius:9px}
.label{font-size:9px;color:#666}
.value{font-size:14px;font-weight:900}
.red{color:#d71919}.green{color:#078524}
.atm{background:#fff4c9;border:3px solid #d9a300}
.title{text-align:center;font-size:20px;font-weight:900;margin-bottom:7px}
.side,.strike,.level{border-radius:10px;padding:7px 3px;text-align:center}
.call{background:#fff0f0}.put{background:#eaf9ed}
.line{display:flex;justify-content:space-between;font-size:11px;padding:3px 1px}
.total{margin-top:4px;padding:5px 1px;border-radius:7px;font-size:13px;font-weight:900}
.calltotal{background:#ffdada;color:#c60000}
.puttotal{background:#d7f4dd;color:#007b21}
.head{text-align:center;font-weight:900;padding:7px;border-radius:9px;margin-bottom:5px}
.reshead{background:#ffe1e1;color:#c60000}
.suphead{background:#def6e3;color:#007b21}
.pair{margin:6px 0}
.strike{background:#f8f9fa;border:1px solid #ddd}
.resstrike{border-left:4px solid #db2424}
.supstrike{border-right:4px solid #148d35}
.strikenum{font-size:17px;font-weight:900;margin-bottom:5px}
.mini{display:grid;grid-template-columns:1fr 1fr;gap:3px}
.mini>div{border-radius:7px;padding:5px 2px}
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
    <div class="ibox"><span class="label">ATM</span><div class="value" id="atm">-</div></div>
    <div class="ibox"><span class="label">Expiry</span><div class="value" id="expiry">-</div></div>
    <div class="ibox"><span class="label">Updated</span><div class="value" id="time">-</div></div>
  </div>
</div>

<div class="card error" id="errorBox"></div>

<div class="card atm">
  <div class="title" id="atmTitle">ATM -</div>

  <div class="two">
    <div class="side call">
      <b class="red">ATM CALL</b>
      <div class="line"><span>Call OI</span><b class="red" id="atmCoi">-</b></div>
      <div class="line"><span>Call Change</span><b id="atmCchg">-</b></div>
      <div class="total calltotal" id="atmCtotal">Total -</div>
    </div>

    <div class="side put">
      <b class="green">ATM PUT</b>
      <div class="line"><span>Put OI</span><b class="green" id="atmPoi">-</b></div>
      <div class="line"><span>Put Change</span><b id="atmPchg">-</b></div>
      <div class="total puttotal" id="atmPtotal">Total -</div>
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
const $=id=>document.getElementById(id);
const color=v=>Number(v||0)>0?"green":Number(v||0)<0?"red":"";

function strikeBox(r,type){
  if(!r)return "<div class='strike'>Data નથી</div>";

  return `<div class="strike ${type}">
    <div class="strikenum">${r.strike}</div>
    <div class="mini">

      <div class="mcall">
        <b class="red small">CALL</b>
        <div class="small">OI</div>
        <div class="smallval red">${r.coi}</div>
        <div class="small">Change</div>
        <div class="smallval ${color(r.cchg_raw)}">${r.cchg}</div>
        <div class="total calltotal">Total ${r.ctotal}</div>
      </div>

      <div class="mput">
        <b class="green small">PUT</b>
        <div class="small">OI</div>
        <div class="smallval green">${r.poi}</div>
        <div class="small">Change</div>
        <div class="smallval ${color(r.pchg_raw)}">${r.pchg}</div>
        <div class="total puttotal">Total ${r.ptotal}</div>
      </div>

    </div>
  </div>`;
}

async function load(){
  try{
    const response=await fetch("/api?t="+Date.now(),{cache:"no-store"});
    const d=await response.json();

    if(!response.ok||d.error)throw new Error(d.error||"Load failed");

    $("errorBox").style.display="none";
    $("nifty").innerText=d.nifty;
    $("atm").innerText=d.atm;
    $("expiry").innerText=d.expiry;
    $("time").innerText=d.time;
    $("atmTitle").innerText="ATM "+d.atm;

    const a=d.atm_data;

    $("atmCoi").innerText=a.coi;
    $("atmCchg").innerText=a.cchg;
    $("atmCchg").className=color(a.cchg_raw);
    $("atmCtotal").innerText="Total "+a.ctotal;

    $("atmPoi").innerText=a.poi;
    $("atmPchg").innerText=a.pchg;
    $("atmPchg").className=color(a.pchg_raw);
    $("atmPtotal").innerText="Total "+a.ptotal;

    $("pairs").innerHTML=d.pairs.map(p=>
      `<div class="pair">
        ${strikeBox(p.upper,"resstrike")}
        ${strikeBox(p.lower,"supstrike")}
      </div>`
    ).join("");

    $("resStrike").innerText=d.resistance.strike;
    $("resDetail").innerHTML=
      "Call OI "+d.resistance.oi+
      "<br>Change "+d.resistance.change+
      "<br><b class='red'>Total "+d.resistance.total+"</b>";

    $("supStrike").innerText=d.support.strike;
    $("supDetail").innerHTML=
      "Put OI "+d.support.oi+
      "<br>Change "+d.support.change+
      "<br><b class='green'>Total "+d.support.total+"</b>";

  }catch(e){
    $("errorBox").style.display="block";
    $("errorBox").innerText=e.message;
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
        "token_configured": bool(TOKEN)
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
