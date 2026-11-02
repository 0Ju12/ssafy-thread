from datetime import date
from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .services import fetch_fx, fetch_market, market_ranks, stock_history, lookup_stocks, stock_quote, refresh_snapshot, captured_history
from django.core.cache import cache
from django.urls import reverse
from django.contrib import messages


def _demo(request):
    val=request.GET.get('demo')
    return (val=='1') if val in ('0','1') else settings.MARKET_SAMPLE_MODE


def _base(request):
    demo=_demo(request)
    market=fetch_market(demo=demo)
    fx=fetch_fx(demo=demo)
    if not demo:
        for idx in market.get('indices',[]):
            idx['history']=captured_history(idx['name'])
        fx['history']=captured_history('USD/KRW',is_fx=True)
    return demo,market,fx


@require_GET
def dashboard(request):
    demo,market,fx=_base(request)
    stocks=market.get('stocks',[])
    ranks=market_ranks(market)
    rising=sum(s['change_pct']>0 for s in stocks)
    falling=sum(s['change_pct']<0 for s in stocks)
    flat=len(stocks)-rising-falling
    return render(request,'market/dashboard.html',{
        'market':market,'fx':fx,'demo':demo,'ranks':ranks,
        'rising':rising,'falling':falling,'flat':flat,'count':len(stocks),
        'is_rank_sample':not demo, 
        'rising_pct':round(rising/len(stocks)*100) if stocks else 0,
        'fall_end_pct':round((rising+falling)/len(stocks)*100) if stocks else 0,
        'market_chart':[{ 'name':idx['name'],'history':idx.get('history',[]),'change_pct':idx['change_pct'] } for idx in market.get('indices',[])],
        'fx_chart':fx.get('history',[]),
    })


@require_GET
def stock_search(request):
    demo,market,fx=_base(request)
    q=request.GET.get('q','').strip()[:60]
    results=[]
    error=''
    if q:
        try:
            results=lookup_stocks(q,demo=demo)
        except ValueError:
            error='수집된 인기 종목 목록에서 검색할 수 없습니다.'
    return render(request,'market/search.html',{'q':q,'results':results,'market':market,'demo':demo,'search_error':error})


@require_GET
def stock_detail(request,code):
    demo,market,fx=_base(request)
    stock=next((s for s in market.get('stocks',[]) if s['code']==code),None)
    if demo:
        if not stock:raise Http404('데모 종목 목록에 없습니다.')
        from datetime import timedelta
        base=stock['price']
        last=date.fromisoformat(stock['date'])
        history=[{'date':(last-timedelta(days=12-i)).isoformat(),
                  'value':round(base*(1+0.007*(i-12)+0.008*((i%4)-2))),
                  'volume':round(stock['volume']*(.65+i*.035))} for i in range(13)]
    else:
        stock=stock_quote(code)
        history=captured_history(code) if stock else []
        if not stock:raise Http404('현재 수집된 종목에 없습니다. 분석하려면 종목명을 입력해 주세요.')
    return render(request,'market/stock_detail.html',{
        'stock':stock,'demo':demo,'market':market,'fx':fx,'history':history,
        'analysis_query':urlencode({'company':stock['name']}),
    })


@require_POST
def refresh(request):
    """같은 웹 화면 Selenium 수집을 수동으로 실행. 중복 제출 제한."""
    lock = 'thread:market:refresh:lock'
    if not cache.add(lock, 'running', timeout=90):
        messages.warning(request, '시장 데이터 수집이 이미 진행 중입니다.')
        return HttpResponseRedirect(reverse('market:dashboard'))
    try:
        result=refresh_snapshot()
        if result['market']['indices'] or result['market']['stocks'] or result['fx']['rates']:
            messages.success(request, '공개 화면에서 수집 가능한 시장 정보를 갱신했습니다.')
        else:
            messages.warning(request, '시장 데이터 수집에 실패했습니다. 사이트 화면 구조를 확인해 주세요.')
    except Exception as exc:
        messages.error(request, f'시장 정보 수집 실패 ({exc.__class__.__name__}). 댓글 분석은 계속 사용할 수 있습니다.')
    finally:
        cache.delete(lock)
    return HttpResponseRedirect(reverse('market:dashboard'))
