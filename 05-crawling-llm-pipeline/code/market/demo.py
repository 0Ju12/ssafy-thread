"""화면 시연 전용 가상 값: 실제 종가/환율이 아닙니다."""
from datetime import date, timedelta

DEMO_NAMES = [
    ('005930','삼성전자','KOSPI',83500,2.31,1132400000000,18750000),
    ('000660','SK하이닉스','KOSPI',224500,4.71,892400000000,4300000),
    ('035420','NAVER','KOSPI',217000,-1.18,345000000000,2100000),
    ('035720','카카오','KOSPI',43900,-3.15,254000000000,6200000),
    ('005380','현대차','KOSPI',239000,1.74,372000000000,1600000),
    ('068270','셀트리온','KOSPI',178000,-2.83,218000000000,1320000),
    ('247540','에코프로비엠','KOSDAQ',113000,7.82,315000000000,2900000),
    ('086520','에코프로','KOSDAQ',72100,-5.24,196000000000,2850000),
    ('028300','HLB','KOSDAQ',74100,0.94,95000000000,1400000),
    ('196170','알테오젠','KOSDAQ',346000,9.18,468000000000,1340000),
    ('293490','카카오게임즈','KOSDAQ',18600,-4.56,85000000000,4800000),
    ('403870','HPSP','KOSDAQ',30500,6.03,124000000000,4100000),
]

def demo_market():
    day = date(2026, 10, 30)
    stocks = [
        dict(code=code,name=name,market=market,price=price,change_pct=pct,
             change=round(price*pct/(100+pct)),volume=vol,value=value,
             market_cap=price*50000000, date=day.isoformat())
        for code,name,market,price,pct,value,vol in DEMO_NAMES
    ]
    indices=[]
    for name,base,growth in [('KOSPI',2674.32,0.65),('KOSDAQ',842.16,-0.41)]:
        history=[]
        for i in range(20):
            when=day-timedelta(days=(19-i))
            if when.weekday()>=5: continue
            if i==19:
                val=base  # 현재 지수 카드와 차트 마지막 값 일치
            elif i==18:
                val=base / (1+growth/100)  # 전일 대비 등락률도 일치
            else:
                val=base*(1+(i-19)*0.003+0.004*((i%5)-2))
            history.append({'date':when.isoformat(),'value':round(val,2)})
        indices.append(dict(name=name,value=base,change_pct=growth,change=round(base*growth/(100+growth),2),history=history,date=day.isoformat()))
    return {'demo':True,'source':'가상 샘플 데이터 · 실제 시세 아님','as_of':'가상 기준일 2026-10-30',
            'indices':indices,'stocks':stocks,'error':'','stock_source':'가상 데모 데이터'}

def demo_fx():
    day = date(2026,10,30)
    historical=[]
    for i in range(30):
        d=day-timedelta(days=29-i)
        if d.weekday()>=5: continue
        val=1392.5 if i==29 else 1392+(i-15)*.7+3*((i%6)-3)
        historical.append({'date':d.isoformat(),'value':round(val,2)})
    return {'demo':True,'source':'가상 샘플 데이터 · 실제 환율 아님','as_of':'가상 기준일 2026-10-30',
            'rates':[dict(symbol='USD/KRW',name='미국 달러',value=1392.5,unit='원 / 1 USD')],
            'history':historical, 'error':''}
