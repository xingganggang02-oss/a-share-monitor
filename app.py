
import os, time
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="A股智能监控")

WATCH = [
    ("600160","巨化股份","SH"),("600176","中国巨石","SH"),("600183","生益科技","SH"),
    ("000977","浪潮信息","SZ"),("002436","兴森科技","SZ"),("002008","大族激光","SZ"),
    ("002428","云南锗业","SZ"),("002636","金安国纪","SZ"),("603256","宏和科技","SH"),
    ("603228","景旺电子","SH"),
]
HOLDINGS = [
    {"code":"000977","name":"浪潮信息","shares":200,"cost":71},
    {"code":"002049","name":"紫光国微","shares":100,"cost":None},
    {"code":"半导体","name":"半导体仓位","shares":7600,"cost":None},
]
FUND = ("513120","港股创新药ETF广发","HK")
BASE = os.getenv("ITICK_BASE_URL","https://api-free.itick.org")
TOKEN = os.getenv("ITICK_TOKEN","")

async def get_json(path, params):
    if not TOKEN:
        return {}
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.get(BASE + path, params=params,
                        headers={"accept":"application/json","token":TOKEN})
        r.raise_for_status()
        return r.json()

def action_for(chp, risk):
    s = 0
    if chp >= 3: s = 3
    elif chp >= 1.5: s = 2
    elif chp >= .3: s = 1
    elif chp <= -4: s = -3
    elif chp <= -2: s = -2
    elif chp <= -.8: s = -1
    if risk: s -= 1
    return ["回避","风险大于机会","逢高减仓","持有观察","小仓试探","分批买入","积极关注"][s+3]

@app.get("/api/status")
async def status():
    if not TOKEN:
        return {"ok":True,"realtime":False,"environment":"待配置 iTick Token",
                "action":"等待","watchlist":[],"holdings":HOLDINGS,"global":{}}
    out = []
    for region in ("SH","SZ"):
        codes = ",".join(x[0] for x in WATCH if x[2]==region)
        j = await get_json("/stock/quotes", {"region":region,"codes":codes})
        for code,d in (j.get("data") or {}).items():
            item = next((x for x in WATCH if x[0]==code),None)
            if item:
                out.append({"code":code,"name":item[1],"price":d.get("ld"),
                            "chp":d.get("chp"),"action":"等待"})
    fundj = await get_json("/fund/quote", {"region":"HK","code":FUND[0]})
    if fundj.get("data"):
        d=fundj["data"]; out.append({"code":FUND[0],"name":FUND[1],"price":d.get("ld"),
                                     "chp":d.get("chp"),"action":"持有观察"})
    gj = await get_json("/indices/quotes", {"region":"GB","codes":"SPX,DJI"})
    global_data = {}
    for k,d in (gj.get("data") or {}).items():
        global_data[k]={"price":d.get("ld"),"chp":d.get("chp")}
    risk = any((x.get("chp") or 0) <= -1 for x in global_data.values())
    for x in out:
        x["action"] = action_for(x.get("chp") or 0, risk)
    env = "风险偏高·控制仓位" if risk else "震荡分化·等待确认"
    return {"ok":True,"realtime":True,"environment":env,"action":"控制仓位" if risk else "等待确认",
            "watchlist":out,"holdings":HOLDINGS,"global":global_data,"server_time":int(time.time())}

@app.get("/", response_class=HTMLResponse)
def home():
    return (Path(__file__).parent/"index.html").read_text(encoding="utf-8")