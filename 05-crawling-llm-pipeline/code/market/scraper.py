"""토스증권 공개 웹페이지의 *화면에 보이는 값*을 Selenium으로 읽는 수집기.

공식 API나 내부 네트워크 엔드포인트를 호출하지 않습니다. 사이트의 공개 화면과
브라우저 DOM 구조가 바뀌면 부분 데이터만 반환합니다. 미확인 값은 만들어내지 않습니다.
"""
from datetime import datetime
import re
import time
from zoneinfo import ZoneInfo

MAIN_URL = 'https://www.tossinvest.com/'
NUMBER = re.compile(r'[+-]?\d[\d,]*(?:\.\d+)?')
PRICE = re.compile(r'(?<!\w)(\d[\d,]*(?:\.\d+)?)\s*원')
PERCENT = re.compile(r'([+\-−]?\d+(?:\.\d+)?)\s*%')
CODE = re.compile(r'/stocks/(?:A)?(\d{6})(?:[/\?#]|$)')
RANK_NAMES = {'rise': '급상승', 'fall': '급하락', 'value': '거래대금', 'volume': '거래량'}


def to_number(text):
    """국문 단위의 숫자. 못 읽는 수치는 None (절대 0으로 임의 대체하지 않음)."""
    m = NUMBER.search(str(text or '').replace('−', '-'))
    if not m:
        return None
    val = float(m.group().replace(',', ''))
    unit = str(text)[m.end():m.end()+2].strip()
    if unit.startswith('조'):
        val *= 10**12
    elif unit.startswith('억'):
        val *= 10**8
    elif unit.startswith('만'):
        val *= 10**4
    return val


def parse_overview(body):
    """홈페이지 '지수 목록'의 첫 가격과 괄호 속 등락률을 읽는다.

    상승/하락 부호를 잃지 않기 위해, 등락 금액이 아닌 가격 뒤의 (+/-)를 읽는다.
    클리핑 영역에서 지수 항목을 찾지 못하면 빈 값으로 처리한다.
    """
    pos = body.find('지수 목록')
    if pos == -1:
        return [], [], ['지수 목록 영역을 찾지 못했습니다.']
    section = body[pos + len('지수 목록'):]
    ends = [section.find(t) for t in ('주요 일정', '실시간 차트', '지금 뜨는 산업') if section.find(t) != -1]
    section = section[:min(ends) if ends else 3500][:3500]
    found = []
    rates = []
    warnings = []
    targets = [('코스피', 'KOSPI', 100.0), ('코스닥', 'KOSDAQ', 100.0), ('달러 환율', 'USD/KRW', 100.0)]
    for label, symbol, minimum in targets:
        match = re.search(r'(?<![가-힣])' + re.escape(label) + r'(?![0-9A-Za-z가-힣])', section)
        if not match:
            warnings.append(f'{label} 표시를 찾지 못했습니다.')
            continue
        remaining = section[match.end(): match.end()+160]
        # 코스피 등 제목 옆의 설명과 각종 숫자가 섞일 수 있으므로 가격 형태와 괄호의 %를 함께 요구한다.
        quote = re.search(r'(\d[\d,]*(?:\.\d+)?)\s*([+\-−]\d[\d,]*(?:\.\d+)?)?\s*\(\s*(\d+(?:\.\d+)?)%\s*\)', remaining)
        if not quote:
            warnings.append(f'{label}의 가격·등락률 형식을 확인할 수 없습니다.')
            continue
        val = to_number(quote.group(1))
        if val is None or val < minimum:
            warnings.append(f'{label}의 값이 비정상적이어서 제외했습니다.')
            continue
        sign = -1 if (quote.group(2) or '').replace('−','-').startswith('-') else 1
        # 등락 폭이 없는 경우 % 방향을 확정할 수 없으므로 전일 대비 표시는 생략한다.
        raw_delta = to_number(quote.group(2)) if quote.group(2) else None
        change = round(raw_delta, 4) if raw_delta is not None else None
        pct = round(sign * float(quote.group(3)), 3) if raw_delta is not None else None
        if symbol == 'USD/KRW':
            rates.append({'symbol':symbol,'name':'미국 달러', 'value':val,
                          'unit':'원 / 1 USD', 'change':change, 'change_pct':pct})
        else:
            found.append({'name':symbol, 'value':val, 'change':change,
                          'change_pct':pct, 'history':[]})
    return found, rates, warnings


def parse_rank_text(body, code_by_name=None, kind='rise', limit=10):
    """현재 선택한 실시간 차트 테이블의 표시 텍스트로 순위 파싱.

    종목 링크에서 종목코드를 확인한 경우에만 상세 URL을 활성화한다.
    테이블 열이 다르거나 순위 본문이 로드되지 않았다면 빈 목록을 돌려준다.
    """
    code_by_name = code_by_name or {}
    anchor = body.find('실시간 차트')
    if anchor < 0:
        return []
    block = body[anchor:]
    begin = re.search(r'순위\s*[·・\-–]', block)
    if not begin:
        return []
    block = block[begin.end():]
    for stopper in ('더 보기', '관심 주식 TOP', '인기 검색'):
        ix = block.find(stopper)
        if ix != -1:
            block = block[:ix]
    lines = [x.strip() for x in block.splitlines() if x.strip()]
    result = []
    used = set()
    for i, line in enumerate(lines):
        if len(result) >= limit:
            break
        if not re.fullmatch(r'(?:[1-9]|[1-9]\d|100)', line):
            continue
        rank = int(line)
        if rank > 100 or rank in used:
            continue
        nxt = lines[i+1:i+9]
        if not nxt:
            continue
        name = nxt[0]
        if len(name) > 70 or name in ('순위', '현재가', '등락률', '거래대금 순'):
            continue
        price_match = next((PRICE.search(x) for x in nxt[1:5] if PRICE.search(x)), None)
        pct_match = next((PERCENT.search(x) for x in nxt[1:6] if PERCENT.search(x)), None)
        if not price_match or not pct_match:
            continue
        price = to_number(price_match.group(1))
        pct = to_number(pct_match.group(1))
        if price is None or price <= 0 or pct is None or abs(pct) > 1000:
            continue
        code = code_by_name.get(name,'')
        val = None
        # 표의 거래대금 셀에서만 거래대금 추출; 시가총액은 읽지 않는다.
        for cell in nxt[3:8]:
            if re.fullmatch(r'[\d,.]+\s*(?:조|억|만)?원', cell):
                val = to_number(cell)
                break
        entry = {'rank':rank,'code':code,'name':name,'market':'미분류',
                 'price':price,'change_pct':pct, 'change':None,
                 'value':val, 'volume':None,'date':'', 'rank_kind':kind}
        result.append(entry)
        used.add(rank)
    if kind == 'rise':
        result=[s for s in result if s['change_pct'] > 0]
    elif kind == 'fall':
        result=[s for s in result if s['change_pct'] < 0]
    return sorted(result,key=lambda s:s['rank'])[:limit]


def _body(driver):
    from selenium.webdriver.common.by import By
    return driver.find_element(By.TAG_NAME, 'body').text


def _stock_links(driver):
    """동일 페이지의 stock href에서 확인한 종목코드만 추출 (추측 금지)."""
    try:
        pairs = driver.execute_script('''
            return [...document.querySelectorAll('a[href*="/stocks/"]')]
              .map(a => ({name:(a.innerText||a.getAttribute('aria-label')||'').trim(),
                            href:a.getAttribute('href')||''}))
              .filter(x=>x.name && x.name.length < 90);
        ''') or []
    except Exception:
        pairs=[]
    result={}
    for pair in pairs:
        m=CODE.search(str(pair.get('href','')))
        name=str(pair.get('name','')).strip().splitlines()[0]
        if m and name:
            result[name]=m.group(1)
    return result


def _switch_rank(driver, text):
    from selenium.webdriver.common.by import By
    # 화면에 노출된 라벨을 가진 실제 클릭 가능 요소만 사용. 내부 비공식 API는 호출하지 않음.
    xpath = ('//*[self::button or @role="tab" or @role="button"]'
             '[normalize-space(.)="%s"]' % text)
    candidates=list(driver.find_elements(By.XPATH, xpath))
    if not candidates:
        # 실제 페이지의 컨트롤이 div/span으로 렌더링되는 경우 정확히 일치하는 텍스트 노드만 대체 탐색
        candidates=driver.find_elements(By.XPATH,
            '//*[not(*) and normalize-space(text())="%s"]' % text)
    for el in candidates:
        try:
            if el.is_displayed() and el.is_enabled():
                driver.execute_script('arguments[0].scrollIntoView({block:"center"});',el)
                try:
                    el.click()
                except Exception:
                    driver.execute_script('arguments[0].click();',el)
                return True
        except Exception:
            continue
    return False


def scrape_snapshot(driver, *, collect_rankings=True, log=lambda msg: None):
    """이미 열린 Chromium/Selenium 세션에서 토스증권 홈 화면을 읽는다.

    하나의 드라이버로 조회하고 댓글 검색도 같은 세션에서 이어서 실행한다.
    자바스크립트로 현재 보여주는 데이터 이외에는 추출하지 않는다.
    """
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    now = datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')
    warnings=[]
    try:
        WebDriverWait(driver, 12).until(lambda d: '지수 목록' in _body(d))
    except Exception:
        warnings.append('홈 화면 지수 영역 로딩이 확인되지 않았습니다.')
    body = _body(driver)
    indices,rates,parse_warn = parse_overview(body)
    warnings.extend(parse_warn)
    ranking_lists = {key: [] for key in RANK_NAMES}
    if collect_rankings:
        # 국내 필터는 가능할 때만 선택한다; 필터가 없다면 해외 종목이 섞일 수 있어 경고한다.
        if _switch_rank(driver, '국내'):
            time.sleep(.5)
        else:
            warnings.append('국내 전용 필터를 선택하지 못했습니다. 순위에 해외종목이 있을 수 있습니다.')
        for key,label in RANK_NAMES.items():
            if not _switch_rank(driver,label):
                warnings.append(f'{label} 순위 버튼을 찾지 못했습니다.')
                continue
            time.sleep(.6)
            rows = parse_rank_text(_body(driver),_stock_links(driver),kind=key,limit=10)
            ranking_lists[key]=rows
            if not rows:
                warnings.append(f'{label} 순위는 읽지 못했습니다. DOM 구조 확인이 필요합니다.')
    stocks = list({(row['code'] or row['name']):row for rows in ranking_lists.values() for row in rows}.values())
    market = {'demo':False,'source':'토스증권 공개 홈페이지 · Selenium 화면 수집',
        'stock_source':'토스증권 화면 표시 시세', 'as_of':now,
        'indices':indices,'stocks':stocks,'ranking_lists':ranking_lists,
        'coverage':'홈페이지에서 확인된 순위 일부', 'error':'',
        'warnings':warnings,'collection_method':'selenium'}
    fx = {'demo':False,'source':'토스증권 공개 홈페이지 · 화면 표시 원/달러',
          'as_of':now,'rates':rates,'history':[], 'error':'' if rates else '원/달러 환율 수집 실패',
          'collection_method':'selenium'}
    if not indices:
        market['error']='코스피·코스닥 지수를 화면에서 읽지 못했습니다.'
    log(f'시장 정보 수집: 지수 {len(indices)}개, 달러 환율 {len(rates)}개, 순위 {sum(map(len,ranking_lists.values()))}개')
    return {'market':market,'fx':fx,'captured_at':now, 'warnings':warnings}
