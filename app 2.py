import os, json, time
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app=FastAPI(title="A股智能监控")
BASE=Path(__file__).parent

WATCH=[
("600160","巨化股份"),("600176","中国巨石"),("600183","生益科技"),
("000977","浪潮信息"),("002436","兴森科技"),("002008","大族激光"),
("002428","云南锗业"),("002636","金安国纪"),("603256","宏和科技"),
("603228","景旺电子"),("513120","港股创新药ETF广发")
]
HOLDINGS=[
{"code":"000977","name":"浪潮信息","shares":200,"cost":71},
{"code":"002049","name":"紫光国微","shares":100,"cost":None},
{"code":"半导体","name":"半导体仓位","shares":7600,"cost":None},
]

@app.get("/api/status")
def status():
    # Production mode is enabled only after a real market-data token is configured.
    realtime=bool(os.getenv("ITICK_TOKEN"))
    return {
      "ok":True,"realtime":realtime,
      "environment":"待实时数据" if not realtime else "实时监控",
      "action":"等待" if not realtime else "计算中",
      "watchlist":WATCH,"holdings":HOLDINGS,
      "server_time":int(time.time())
    }

@app.get("/",response_class=HTMLResponse)
def home():
    return (BASE/"index.html").read_text(encoding="utf-8")
