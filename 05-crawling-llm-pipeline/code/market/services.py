"""Selenium 공개 화면 수집 결과를 캐시해 시장 페이지와 댓글 결과에서 재사용.

Open API, 토스 내부 비공개 API, Frankfurter 등 외부 시세 API는 호출하지 않는다.
"""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache

from .demo import demo_market, demo_fx
from .scraper import scrape_snapshot

CACHE_KEY = 'thread:selenium:market:v1'


def empty_snapshot(message='수집된 시장 정보가 없습니다. 댓글 분석을 시작하거나 수동 새로고침을 이용하세요.'):
    at = ''
    return {'market':{'demo':False,'source':'토스증권 공개 화면 · Selenium',
                     'stock_source':'토스증권 화면 표시 시세','as_of':at,
                     'indices':[],'stocks':[],'ranking_lists':{},'error':message,
                     'coverage':'화면에 표시된 순위만','collection_method':'selenium'},
            'fx':{'demo':False,'source':'토스증권 공개 화면 · Selenium',
                  'as_of':at,'rates':[],'history':[],'error':message,
                  'collection_method':'selenium'},
            'captured_at':'','warnings':[]}


def demo_snapshot():
    return {'market':demo_market(),'fx':demo_fx(),
            'captured_at':'가상 시연용', 'warnings':['데모 값: 실제 시세가 아닙니다.']}


def capture_with_driver(driver, log=lambda message: None, save=True):
    """같은 크롬 세션에서 홈 시장정보 수집 후 댓글 검색을 이어서 수행하기 위한 진입점."""
    snapshot = scrape_snapshot(driver, log=log)
    if save and (snapshot['market']['indices'] or snapshot['market']['stocks'] or snapshot['fx']['rates']):
        cache.set(CACHE_KEY, snapshot, timeout=max(60,settings.MARKET_CACHE_SECONDS))
        from .models import MarketCapture
        MarketCapture.objects.create(payload=snapshot)
    return snapshot


def cached_snapshot():
    return cache.get(CACHE_KEY) or empty_snapshot()


def fetch_market(demo=False):
    return demo_market() if demo else cached_snapshot()['market']


def fetch_fx(demo=False):
    return demo_fx() if demo else cached_snapshot()['fx']


def market_ranks(market):
    source = market.get('ranking_lists') or {}
    output={}
    for kind in ('rise','fall','value','volume'):
        rows=source.get(kind,[])
        if not rows and market.get('demo'):
            stocks=market.get('stocks',[])
            if kind == 'rise':rows=sorted((r for r in stocks if r['change_pct']>0),key=lambda r:-r['change_pct'])
            elif kind == 'fall':rows=sorted((r for r in stocks if r['change_pct']<0),key=lambda r:r['change_pct'])
            elif kind == 'value':rows=sorted(stocks,key=lambda r:-r['value'])
            else:rows=sorted(stocks,key=lambda r:-r['volume'])
        output[kind]={m:[r for r in rows if m=='ALL' or r.get('market')==m][:10]
                      for m in ('ALL','KOSPI','KOSDAQ')}
    return output


def lookup_stocks(query,demo=False):
    market=fetch_market(demo)
    needle=query.strip().lower()
    if not needle:return []
    return [x for x in market.get('stocks',[])
            if needle in x['name'].lower() or (x.get('code') and needle in x['code'])][:30]


def stock_quote(code):
    return next((x for x in fetch_market().get('stocks',[]) if x.get('code')==code),None)


def stock_history(code):
    # 공개 웹 화면에서 전체 기간별 OHLCV를 확인할 수 없으면 임의로 만들지 않는다.
    return []


def refresh_snapshot(headless=None):
    """수동 갱신 버튼용 Selenium 브라우저 1회 실행 (댓글 요청과 별개의 접근)."""
    from comments.services.crawler import get_driver, open_main, close_popups
    driver=get_driver(settings.CRAWLER_HEADLESS if headless is None else headless)
    try:
        open_main(driver)
        close_popups(driver)
        return capture_with_driver(driver)
    finally:
        driver.quit()


def captured_history(symbol, is_fx=False, limit=35):
    """실제로 수집된 서로 다른 시점의 화면 값만으로 그린 그래프 (인위적 보간 없음)."""
    from .models import MarketCapture
    rows=list(MarketCapture.objects.order_by('-created_at').only('payload','created_at')[:max(limit*3,60)])
    points=[]
    for row in reversed(rows):
        part='fx' if is_fx else 'market'
        key='rates' if is_fx else 'indices'
        entries=row.payload.get(part,{}).get(key,[])
        if not is_fx and symbol not in ('KOSPI','KOSDAQ'):
            entries=row.payload.get('market',{}).get('stocks',[])
            found=next((x for x in entries if x.get('code')==symbol),None)
        else:
            found=next((x for x in entries if x.get('symbol' if is_fx else 'name')==symbol),None)
        if found and found.get('value') is not None:
            points.append({'date':row.created_at.astimezone(ZoneInfo('Asia/Seoul')).strftime('%m/%d %H:%M'),
                           'value':found['value']})
    return points[-limit:]
