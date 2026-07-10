from flask import Flask, render_template_string, jsonify
import requests, os
from datetime import datetime

app = Flask(__name__)
TOKEN=os.environ.get("UPSTOX_TOKEN")
UNDERLYING="NSE_INDEX|Nifty 50"; STEP=50; AROUND=5

def H(): return {"Accept":"application/json","Authorization":"Bearer "+TOKEN}
def fmt(n):
    try:
        n=float(n); s="+" if n>0 else "-" if n<0 else ""; n=abs(n)
        if n>=10000000: return s+str(round(n/10000000,2))+"Cr"
        if n>=100000: return s+str(round(n/100000,2))+"L"
        if n>=1000: return s+str(round(n/1000,1))+"K"
        return s+str(int(n))
    except: return "-"
def chg(md):
    for k in ["oi_day_change","oi_change","change_oi","oi_change_value","change_in_oi"]:
        v=md.get(k)
        if v not in [None,""]: return float(v or 0)
    oi=float(md.get("oi",0) or 0); prev=float(md.get("previous_oi",0) or md.get("prev_oi",0) or md.get("close_oi",0) or 0)
    return oi-prev if prev else 0
def expiry():
    e=os.environ.get("EXPIRY_DATE")
    if e: return e
    js=requests.get("https://api.upstox.com/v2/option/contract",headers=H(),params={"instrument_key":UNDERLYING},timeout=10).json()
    ex=sorted(list(set([x.get("expiry") for x in js.get("data",[]) if x.get("expiry")])))
    if not ex: raise Exception("EXPIRY_DATE add karo")
    return ex[0]
def prob(score): return max(5,min(95,round(score)))

@app.route("/api")
def api():
    if not TOKEN: return jsonify({"error":"UPSTOX_TOKEN missing"})
    try:
        l=requests.get("https://api.upstox.com/v2/market-quote/ltp",headers=H(),params={"instrument_key":UNDERLYING},timeout=10).json()
        nifty=float(l["data"]["NSE_INDEX:Nifty 50"]["last_price"])
        exp=expiry()
        oc=requests.get("https://api.upstox.com/v2/option/chain",headers=H(),params={"instrument_key":UNDERLYING,"expiry_date":exp},timeout=15).json()
        data=oc.get("data",[])
    except Exception as e:
        return jsonify({"error":str(e)})

    atm=round(nifty/STEP)*STEP; low=atm-AROUND*STEP; high=atm+AROUND*STEP
    rows=[]; coi=cchg=ctot=poi=pchg=ptot=0
    for x in data:
        st=int(float(x.get("strike_price",0)))
        if st<low or st>high: continue
        c=x.get("call_options",{}).get("market_data",{}); p=x.get("put_options",{}).get("market_data",{})
        co=float(c.get("oi",0) or 0); po=float(p.get("oi",0) or 0)
        cc=chg(c); pc=chg(p); ct=co+cc; pt=po+pc; diff=pt-ct
        coi+=co; cchg+=cc; ctot+=ct; poi+=po; pchg+=pc; ptot+=pt
        rows.append({"strike":st,"atm":st==atm,"co":co,"cc":cc,"ct":ct,"pt":pt,"pc":pc,"po":po,"diff":diff,
        "cof":fmt(co),"ccf":fmt(cc),"ctf":fmt(ct),"ptf":fmt(pt),"pcf":fmt(pc),"pof":fmt(po),"difff":fmt(diff)})

    rows=sorted(rows,key=lambda x:x["strike"])
    if not rows: return jsonify({"error":"No data"})

    top_call=sorted(rows,key=lambda x:x["ct"],reverse=True)[:3]
    top_put=sorted(rows,key=lambda x:x["pt"],reverse=True)[:3]
    call_r={r["strike"]:i+1 for i,r in enumerate(top_call)}
    put_r={r["strike"]:i+1 for i,r in enumerate(top_put)}
    for r in rows:
        r["cr"]=call_r.get(r["strike"],0); r["pr"]=put_r.get(r["strike"],0)
        r["cs"]="⭐⭐⭐" if r["cr"]==1 else "⭐⭐" if r["cr"]==2 else "⭐" if r["cr"]==3 else ""
        r["ps"]="⭐⭐⭐" if r["pr"]==1 else "⭐⭐" if r["pr"]==2 else "⭐" if r["pr"]==3 else ""

    pcr=round(poi/coi,2) if coi else 0
    diffsum=ptot-ctot
    res=top_call[0]; sup=top_put[0]

    res_net=res["ct"]-res["pt"]
    sup_net=sup["pt"]-sup["ct"]

    bull_score=50
    if pchg>cchg: bull_score+=20
    else: bull_score-=20
    if ptot>ctot: bull_score+=15
    else: bull_score-=15
    if pcr>1: bull_score+=10
    else: bull_score-=10
    if abs(res["strike"]-sup["strike"])<=50: bull_score-=5

    call_prob=prob(bull_score)
    put_prob=prob(100-bull_score)

    if abs(call_prob-put_prob)<12:
        decision="🟡 SIDEWAYS / WAIT"; color="#fff3cd"
        simple="બંને side નજીક છે, breakout પહેલાં wait કરવું સારું."
    elif call_prob>put_prob:
        decision="🟢 CALL SIDE WATCH"; color="#d9fbe6"
        simple=f"{sup['strike']} support strong છે, market ઉપર જવાની chance વધારે."
    else:
        decision="🔴 PUT SIDE WATCH"; color="#ffe1e1"
        simple=f"{res['strike']} resistance strong છે, market નીચે આવવાની chance વધારે."

    return jsonify({
        "nifty":nifty,"atm":atm,"expiry":exp,"pcr":pcr,"decision":decision,"color":color,"simple":simple,
        "coi":fmt(coi),"cchg":fmt(cchg),"ctot":fmt(ctot),"poi":fmt(poi),"pchg":fmt(pchg),"ptot":fmt(ptot),"diffsum":fmt(diffsum),
        "res_strike":res["strike"],"res_call":fmt(res["ct"]),"res_put":fmt(res["pt"]),"res_net":fmt(res_net),
        "sup_strike":sup["strike"],"sup_put":fmt(sup["pt"]),"sup_call":fmt(sup["ct"]),"sup_net":fmt(sup_net),
        "call_prob":call_prob,"put_prob":put_prob,
        "top_call":[{"strike":r["strike"],"v":fmt(r["ct"])} for r in top_call],
        "top_put":[{"strike":r["strike"],"v":fmt(r["pt"])} for r in top_put],
        "rows":rows,"time":datetime.now().strftime("%H:%M:%S")
    })

HTML="""
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty OI Easy</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0;padding:6px}.card{background:white;padding:10px;margin:6px;border-radius:14px;box-shadow:0 2px 5px #ddd}
.signal{padding:13px;border-radius:14px;text-align:center;font-size:19px;font-weight:bold;margin:6px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.box{background:#f8f9fa;border-radius:12px;padding:8px;text-align:center}.label{font-size:11px;color:#555}.val{font-size:17px;font-weight:bold}.big{font-size:23px;font-weight:bold}
.green{color:green;font-weight:bold}.red{color:red;font-weight:bold}.blue{color:#0754c7;font-weight:bold}table{width:100%;border-collapse:collapse;font-size:10.5px}
td,th{padding:5px 3px;border-bottom:1px solid #ddd;text-align:right}td:first-child,th:first-child{text-align:center}.atm{background:#fff3cd;font-weight:bold}
.callhi{background:#ffe1e1!important;font-weight:bold}.puthi{background:#d9fbe6!important;font-weight:bold}.info{font-size:14px;line-height:1.45}.small{text-align:center;color:#666;font-size:12px}
</style></head><body>

<div class="card">NIFTY LIVE: <span class="big" id="nifty">Loading...</span><br>PCR: <span id="pcr" class="blue">-</span> | ATM: <span id="atm" class="blue">-</span> | Time: <span id="time">-</span></div>
<div class="signal" id="decision">Loading...</div>

<div class="card"><h3>ATM ±5 Strike</h3><table><thead><tr><th>Strike</th><th>Call OI</th><th>Call Chg</th><th>Call Total</th><th>Put Total</th><th>Put Chg</th><th>Put OI</th><th>Diff</th></tr></thead><tbody id="tb"></tbody></table></div>

<div class="card"><h3>Strong Support / Resistance</h3><div class="grid">
<div class="box"><div class="label">Resistance CE</div><div class="val red" id="res">-</div></div>
<div class="box"><div class="label">Support PE</div><div class="val green" id="sup">-</div></div>
</div></div>

<div class="card"><h3>Easy Pressure Analysis</h3>
<div class="signal" id="simple">-</div>
<div class="grid">
<div class="box"><div class="label">Resistance Strike</div><div class="val red" id="res_strike">-</div></div>
<div class="box"><div class="label">Support Strike</div><div class="val green" id="sup_strike">-</div></div>
<div class="box"><div class="label">Resistance Call Total</div><div class="val red" id="res_call">-</div></div>
<div class="box"><div class="label">Resistance Put Total</div><div class="val green" id="res_put">-</div></div>
<div class="box"><div class="label">Resistance Net</div><div class="val red" id="res_net">-</div></div>
<div class="box"><div class="label">Support Net</div><div class="val green" id="sup_net">-</div></div>
<div class="box"><div class="label">CALL Chance</div><div class="val green" id="call_prob">-</div></div>
<div class="box"><div class="label">PUT Chance</div><div class="val red" id="put_prob">-</div></div>
</div>
<p class="info">Sideways ત્યારે થાય છે જ્યારે Support અને Resistance બંને નજીક હોય અથવા Call/Put pressureમાં મોટો difference ન હોય.</p>
</div>

<div class="card"><h3>Summary</h3><div class="grid">
<div class="box"><div class="label">Call Total</div><div class="val red" id="ctot">-</div></div>
<div class="box"><div class="label">Put Total</div><div class="val green" id="ptot">-</div></div>
<div class="box"><div class="label">Call Chg</div><div class="val red" id="cchg">-</div></div>
<div class="box"><div class="label">Put Chg</div><div class="val green" id="pchg">-</div></div>
<div class="box"><div class="label">Put-Call Diff</div><div class="val blue" id="diffsum">-</div></div>
<div class="box"><div class="label">Expiry</div><div class="val" id="exp">-</div></div>
</div></div>

<p class="small">Auto refresh 2 sec</p>

<script>
async function load(){
 let r=await fetch('/api'); let d=await r.json();
 if(d.error){decision.innerText=d.error;decision.style.background='#ffe1e1';return;}
 nifty.innerText=d.nifty; pcr.innerText=d.pcr; atm.innerText=d.atm; time.innerText=d.time; exp.innerText=d.expiry;
 decision.innerText=d.decision; decision.style.background=d.color; simple.innerText=d.simple; simple.style.background=d.color;
 ctot.innerText=d.ctot; ptot.innerText=d.ptot; cchg.innerText=d.cchg; pchg.innerText=d.pchg; diffsum.innerText=d.diffsum;
 res_strike.innerText=d.res_strike; sup_strike.innerText=d.sup_strike; res_call.innerText=d.res_call; res_put.innerText=d.res_put;
 res_net.innerText=d.res_net; sup_net.innerText=d.sup_net; call_prob.innerText=d.call_prob+"%"; put_prob.innerText=d.put_prob+"%";
 res.innerHTML=d.top_call.map((x,i)=>`${i+1}) ${x.strike} ${x.v}`).join('<br>');
 sup.innerHTML=d.top_put.map((x,i)=>`${i+1}) ${x.strike} ${x.v}`).join('<br>');
 let html='';
 d.rows.forEach(x=>{
  html+=`<tr class="${x.atm?'atm':''}"><td>${x.strike}</td><td class="red">${x.cof}</td><td class="${x.cc<0?'green':'red'}">${x.ccf}</td><td class="${x.cr?'callhi':'red'}">${x.ctf} ${x.cs}</td><td class="${x.pr?'puthi':'green'}">${x.ptf} ${x.ps}</td><td class="${x.pc>0?'green':'red'}">${x.pcf}</td><td class="green">${x.pof}</td><td class="${x.diff>=0?'green':'red'}">${x.difff}</td></tr>`;
 });
 tb.innerHTML=html;
}
load(); setInterval(load,2000);
</script></body></html>
"""
@app.route("/")
def home(): return render_template_string(HTML)
