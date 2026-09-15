import os,time
from pathlib import Path
from typing import Any
import httpx
from fastapi import FastAPI,HTTPException,Query
from fastapi.responses import HTMLResponse
app=FastAPI(title='A股智能监控')
WATCH=[('600160','巨化股份','SH'),('600176','中国巨石','SH'),('600183','生益科技','SH'),('000977','浪潮信息','SZ'),('002436','兴森科技','SZ'),('002008','大族激光','SZ'),('002428','云南锗业','SZ'),('002636','金安国纪','SZ'),('603256','宏和科技','SH'),('603228','景旺电子','SH')]
HOLDINGS=[{'code':'000977','name':'浪潮信息','shares':200,'cost':71},{'code':'002049','name':'紫光国微','shares':100,'cost':None},{'code':'半导体','name':'半导体仓位','shares':7600,'cost':None}]
BASE=os.getenv('ITICK_BASE_URL','https://api-free.itick.org').rstrip('/')
TOKEN=os.getenv('ITICK_TOKEN','')
async def get_json(path,params):
    if not TOKEN:return {}
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r=await c.get(BASE+path,params=params,headers={'accept':'application/json','token':TOKEN});r.raise_for_status();x=r.json();return x if isinstance(x,dict) else {}
    except Exception as e: print('iTick',path,e);return {}
def data(x): return x.get('data') if isinstance(x,dict) else None
def region(code):
    if code.startswith(('6','68')):return 'SH'
    if code.startswith(('0','2','3')):return 'SZ'
    raise HTTPException(400,'目前支持沪深A股：6/68沪市，0/2/3深市')
def f(x):
    try:return float(x)
    except:return None
async def globals_():
    d=data(await get_json('/indices/quotes',{'region':'GB','codes':'SPX,DJI'}));out={}
    if isinstance(d,dict):
        for k,v in d.items():
            if isinstance(v,dict):out[k]={'price':v.get('ld'),'chp':v.get('chp'),'time':v.get('t')}
    risk=sum(1 for v in out.values() if (f(v.get('chp')) or 0)<=-1)>=1
    return out,risk
async def quote_info(code):
    rg=region(code);q=data(await get_json('/stock/quote',{'region':rg,'code':code}));
    if not isinstance(q,dict) or q.get('ld') is None:raise HTTPException(404,'没有拿到该股票行情，请检查代码或 iTick 权限')
    inf=data(await get_json('/stock/info',{'type':'stock','region':rg,'code':code}));inf=inf if isinstance(inf,dict) else {}
    hi,lo,p=f(q.get('h')),f(q.get('l')),f(q.get('ld'));pos=round((p-lo)/(hi-lo)*100,1) if hi is not None and lo is not None and p is not None and hi>lo else None
    return {'code':code,'region':rg,'name':inf.get('n') or code,'industry':inf.get('s'),'sector':inf.get('i'),'pe':inf.get('pet'),'market_cap':inf.get('mcb'),'description':inf.get('bd'),'price':q.get('ld'),'open':q.get('o'),'prev_close':q.get('p'),'high':q.get('h'),'low':q.get('l'),'change':q.get('ch'),'change_pct':q.get('chp'),'volume':q.get('v'),'turnover':q.get('tu'),'trade_status':q.get('ts'),'trade_time':q.get('t'),'day_position':pos}
def action(pct,risk,pos=None):
    p=f(pct) or 0;s=3 if p>=3 else 2 if p>=1.5 else 1 if p>=.3 else -3 if p<=-4 else -2 if p<=-2 else -1 if p<=-.8 else 0
    if p>=3 and pos is not None and pos>85:s-=1
    if risk:s-=1
    s=max(-3,min(3,s));return {-3:'回避',-2:'风险大于机会',-1:'逢高减仓',0:'持有观察',1:'小仓试探',2:'分批买入',3:'积极关注'}[s]
def reason(a,p,risk,pe):
    p=f(p) or 0;pe=f(pe);r='海外风险偏高，降低进攻级别。' if risk else '海外风险暂未形成明显压制。'
    if a=='分批买入':return '短线表现偏强，适合分批验证，不追单点重仓；'+r
    if a=='积极关注':return '短线强势明显，可加入重点观察；'+r
    if a=='小仓试探':return '方向略偏强，先小仓验证；'+r
    if a=='逢高减仓':return f'当前涨跌幅约 {p:.2f}%，短线承压；'+r
    if a=='风险大于机会':return f'当前回撤约 {abs(p):.2f}%，风险收益比偏弱；'+r
    if a=='回避':return f'短线跌幅较大，优先控制风险；'+r
    if pe is not None and pe>60:return f'行情尚可但估值偏高（PE约{pe:.1f}）；'+r
    return '暂未出现足够强的趋势信号；'+r
@app.get('/api/status')
async def status():
    if not TOKEN:return {'ok':True,'realtime':False,'environment':'待配置iTick Token','action':'等待','watchlist':[],'holdings':HOLDINGS,'global':{},'server_time':int(time.time())}
    g,risk=await globals_();out=[]
    for c,n,rg in WATCH:
        try:
            x=await quote_info(c);x['name']=n;x['action']=action(x['change_pct'],risk,x['day_position']);x['reason']=reason(x['action'],x['change_pct'],risk,x['pe']);out.append(x)
        except Exception as e:print('watch',c,e)
    return {'ok':True,'realtime':True,'environment':'风险偏高·控制仓位' if risk else '震荡分化·等待确认','action':'控制仓位' if risk else '等待确认','watchlist':out,'holdings':HOLDINGS,'global':g,'server_time':int(time.time())}
@app.get('/api/analyze')
async def analyze(code:str=Query(...,min_length=4,max_length=6)):
    code=code.strip()
    if not code.isdigit():raise HTTPException(400,'请输入4—6位数字股票代码')
    if not TOKEN:raise HTTPException(503,'iTick Token尚未配置')
    g,risk=await globals_();x=await quote_info(code);a=action(x['change_pct'],risk,x['day_position']);x['action']=a;x['reason']=reason(a,x['change_pct'],risk,x['pe']);x['global']=g;x['risk']=risk
    score=50;p=f(x['change_pct']) or 0;pe=f(x['pe']);score+=15 if p>=2 else 8 if p>=.5 else -18 if p<=-3 else -10 if p<=-1 else 0;score-=10 if risk else 0;score-=8 if pe and pe>80 else 0;score+=5 if pe and pe<25 else 0;x['score']=max(0,min(100,score));x['position']='总资金5%—10%内，分2—3批验证' if a in ('分批买入','积极关注') else '计划仓位的1/3以内先试' if a=='小仓试探' else '不急于加仓，等待趋势确认' if a=='持有观察' else '优先控制风险，不主动扩大仓位';return x
@app.get('/',response_class=HTMLResponse)
def home():
    p=Path(__file__).parent/'index.html';return p.read_text(encoding='utf-8') if p.exists() else '<h2>A股智能监控</h2>'
