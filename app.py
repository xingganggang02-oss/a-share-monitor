import os
import time
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="A股智能监控")

WATCH = [
    ("600160", "巨化股份", "SH"),
    ("600176", "中国巨石", "SH"),
    ("600183", "生益科技", "SH"),
    ("000977", "浪潮信息", "SZ"),
    ("002436", "兴森科技", "SZ"),
    ("002008", "大族激光", "SZ"),
    ("002428", "云南锗业", "SZ"),
    ("002636", "金安国纪", "SZ"),
    ("603256", "宏和科技", "SH"),
    ("603228", "景旺电子", "SH"),
]

HOLDINGS = [
    {"code": "000977", "name": "浪潮信息", "shares": 200, "cost": 71},
    {"code": "002049", "name": "紫光国微", "shares": 100, "cost": None},
    {"code": "半导体", "name": "半导体仓位", "shares": 7600, "cost": None},
]

FUND = ("513120", "港股创新药ETF广发", "HK")

BASE = os.getenv("ITICK_BASE_URL", "https://api-free.itick.org").rstrip("/")
TOKEN = os.getenv("ITICK_TOKEN", "")


async def get_json(path, params):
    if not TOKEN:
        return {}

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                BASE + path,
                params=params,
                headers={
                    "accept": "application/json",
                    "token": TOKEN,
                },
            )
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        print(f"iTick request error: {path}: {exc}")
        return {}


def action_for(chp, risk):
    try:
        chp = float(chp or 0)
    except (TypeError, ValueError):
        chp = 0

    if chp >= 3:
        score = 3
    elif chp >= 1.5:
        score = 2
    elif chp >= 0.3:
        score = 1
    elif chp <= -4:
        score = -3
    elif chp <= -2:
        score = -2
    elif chp <= -0.8:
        score = -1
    else:
        score = 0

    if risk:
        score -= 1

    score = max(-3, min(3, score))

    actions = {
        -3: "回避",
        -2: "风险大于机会",
        -1: "逢高减仓",
         0: "持有观察",
         1: "小仓试探",
         2: "分批买入",
         3: "积极关注",
    }

    return actions[score]


def normalize_quotes(data):
    if not data:
        return {}

    if isinstance(data, dict):
        quotes = data.get("data", {})
        if isinstance(quotes, dict):
            return quotes
        if isinstance(quotes, list):
            result = {}
            for item in quotes:
                if isinstance(item, dict):
                    code = item.get("code") or item.get("symbol")
                    if code:
                        result[str(code)] = item
            return result

    if isinstance(data, list):
        result = {}
        for item in data:
            if isinstance(item, dict):
                code = item.get("code") or item.get("symbol")
                if code:
                    result[str(code)] = item
        return result

    return {}


@app.get("/api/status")
async def status():
    if not TOKEN:
        return {
            "ok": True,
            "realtime": False,
            "environment": "待配置 iTick Token",
            "action": "等待",
            "watchlist": [],
            "holdings": HOLDINGS,
            "global": {},
            "server_time": int(time.time()),
        }

    out = []

    for region in ("SH", "SZ"):
        codes = ",".join(
            item[0] for item in WATCH if item[2] == region
        )

        if not codes:
            continue

        data = await get_json(
            "/stock/quotes",
            {
                "region": region,
                "codes": codes,
            },
        )

        quotes = normalize_quotes(data)

        for code, quote in quotes.items():
            code = str(code)

            item = next(
                (x for x in WATCH if x[0] == code),
                None,
            )

            if not item or not isinstance(quote, dict):
                continue

            out.append(
                {
                    "code": code,
                    "name": item[1],
                    "price": quote.get("ld"),
                    "chp": quote.get("chp"),
                    "action": "等待",
                }
            )

    fund_data = await get_json(
        "/fund/quote",
        {
            "region": "HK",
            "code": FUND[0],
        },
    )

    fund_quotes = normalize_quotes(fund_data)

    fund_quote = None

    if isinstance(fund_data, dict):
        raw = fund_data.get("data")

        if isinstance(raw, dict):
            if "ld" in raw or "chp" in raw:
                fund_quote = raw
            elif FUND[0] in raw:
                fund_quote = raw[FUND[0]]

    if fund_quote is None and fund_quotes:
        fund_quote = next(iter(fund_quotes.values()), None)

    if isinstance(fund_quote, dict):
        out.append(
            {
                "code": FUND[0],
                "name": FUND[1],
                "price": fund_quote.get("ld"),
                "chp": fund_quote.get("chp"),
                "action": "持有观察",
            }
        )

    global_data = {}

    global_response = await get_json(
        "/indices/quotes",
        {
            "region": "GB",
            "codes": "SPX,DJI",
        },
    )

    global_quotes = normalize_quotes(global_response)

    for code, quote in global_quotes.items():
        if not isinstance(quote, dict):
            continue

        global_data[str(code)] = {
            "price": quote.get("ld"),
            "chp": quote.get("chp"),
        }

    risk = any(
        float(item.get("chp") or 0) <= -1
        for item in global_data.values()
        if isinstance(item, dict)
    )

    for item in out:
        item["action"] = action_for(
            item.get("chp"),
            risk,
        )

    if risk:
        environment = "风险偏高·控制仓位"
        overall_action = "控制仓位"
    else:
        environment = "震荡分化·等待确认"
        overall_action = "等待确认"

    return {
        "ok": True,
        "realtime": True,
        "environment": environment,
        "action": overall_action,
        "watchlist": out,
        "holdings": HOLDINGS,
        "global": global_data,
        "server_time": int(time.time()),
    }


@app.get("/", response_class=HTMLResponse)
def home():
    index_file = Path(__file__).parent / "index.html"

    if not index_file.exists():
        return "<h2>A股智能监控</h2><p>index.html 不存在</p>"

    return index_file.read_text(encoding="utf-8")
