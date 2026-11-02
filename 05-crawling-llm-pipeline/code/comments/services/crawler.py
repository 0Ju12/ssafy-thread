"""
crawler.py : 토스증권 커뮤니티 댓글 수집 모듈 (F603, F604)

06_pipeline/crawler.py 를 가져와 다음을 보완했습니다.
  - 실제종목명(stock_name) 추출 추가 (F602 저장 항목)
  - 결과를 리스트 대신 딕셔너리로 반환 : 상태(status)로 실패 원인을 구분 (F611)
  - print 대신 log 콜백 : 터미널 출력 + 웹 화면 진행 상황 스트리밍 (F603 선택)
  - USE_SAMPLE_DATA 모드 : 토스증권 접속 없이 샘플 댓글로 개발·테스트

    from comments.services.crawler import fetch_comments
    result = fetch_comments('삼성', limit=20)
    # {'status': 'ok', 'stock_name': '삼성전자', 'stock_code': 'A005930', 'comments': [...]}
"""

import json
import os
import re
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

MAIN_URL = os.getenv('TOSS_MAIN_URL', 'https://www.tossinvest.com/')

# 수집 결과 상태
STATUS_OK = 'ok'
STATUS_NO_COMPANY = 'no_company'  # 검색 결과(종목 페이지)가 없음
STATUS_NO_COMMENTS = 'no_comments'  # 종목은 찾았지만 댓글이 없음
STATUS_ERROR = 'error'  # 브라우저 실행 실패 등 그 밖의 오류


# ------------------------------------------------------------
# 브라우저 실행
# ------------------------------------------------------------
def get_driver(headless=True):
    """옵션을 적용한 크롬 브라우저를 실행해 돌려준다"""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument('--lang=ko-KR')
    if headless:
        # 창 없이 백그라운드로 실행 (웹 서비스 안에서 실행할 때)
        chrome_options.add_argument('--headless=new')
        # 창 크기를 지정하지 않으면 작은 화면(모바일) 배치로 그려질 수 있음
        chrome_options.add_argument('--window-size=1920,1080')
    # (선택) 크롬 실행 파일 위치를 직접 지정해야 할 때만 .env 에 CHROME_BINARY 설정
    if os.getenv('CHROME_BINARY'):
        chrome_options.binary_location = os.getenv('CHROME_BINARY')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

    # 1순위 : webdriver-manager 로 설치된 크롬 버전에 맞는 ChromeDriver 를 내려받아 사용
    service = get_driver_service()
    if service is not None:
        try:
            return webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:  # 버전 불일치(WebDriverException), 잘못된 경로(OSError) 등
            print(f'[안내] webdriver-manager 드라이버 실행 실패 -> Selenium 기본 관리로 재시도 ({e.__class__.__name__})')

    # 2순위 : Selenium 4.6+ 내장 Selenium Manager 가 드라이버를 자동으로 준비
    return webdriver.Chrome(options=chrome_options)


def get_driver_service():
    """webdriver-manager 로 ChromeDriver 를 준비해 Service 로 돌려준다 (실패하면 None)

    .env 에 USE_WEBDRIVER_MANAGER=0 을 넣으면 사용하지 않음
    """
    if os.getenv('USE_WEBDRIVER_MANAGER', '1') != '1':
        return None
    try:
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        return Service(ChromeDriverManager().install())
    except Exception as e:  # 미설치, 네트워크 차단 등
        print(f'[안내] webdriver-manager 사용 불가 -> Selenium 기본 관리 사용 ({e.__class__.__name__})')
        return None


# ------------------------------------------------------------
# 06_pipeline/crawler.py 에서 가져온 함수 (log 콜백만 추가)
# ------------------------------------------------------------
def open_main(driver, log=print):
    """토스증권 메인 페이지에 접속하고, 화면이 그려질 때까지 기다린다"""
    driver.get(MAIN_URL)
    # 왼쪽 메뉴(#ts-lnb)는 자바스크립트가 화면을 그린 뒤에 나타나는 요소
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '#ts-lnb'))
    )
    log('토스증권 메인 페이지 로딩 완료')


def close_popups(driver):
    """첫 진입 시 뜨는 안내 팝업의 닫기 버튼을 모두 누른다"""
    time.sleep(1)  # 팝업은 페이지가 그려진 뒤 조금 늦게 뜨는 경우가 있음
    for close_btn in driver.find_elements(By.XPATH, "//button[@aria-label='닫기']"):
        try:
            if close_btn.is_displayed():
                # 다른 요소에 가려진 버튼도 누를 수 있도록 자바스크립트로 클릭
                driver.execute_script('arguments[0].click();', close_btn)
                time.sleep(0.5)
        except Exception:
            pass  # 닫기에 실패해도 진행에는 큰 문제가 없음


def search_company(driver, company_name, log=print):
    """'/' 단축키로 검색창을 열고 회사명을 검색한다

    검색 모달은 결과 목록의 "최상단 종목"에 자동으로 포커스를 주므로
    Enter 를 누르면 최상단 종목 페이지로 이동한다 (F603 : '삼성' -> '삼성전자')
    """
    close_popups(driver)

    # 단축키는 페이지 전체(body)에 포커스가 있어야 동작
    driver.execute_script('document.activeElement.blur(); document.body.focus();')
    ActionChains(driver).send_keys('/').perform()

    search_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='검색어를 입력해주세요']")
        )
    )
    search_input.send_keys(company_name)
    # 일부 문자열('삼성')을 입력하면 검색 결과 목록이 늦게 그려질 수 있음
    # -> 목록이 갱신될 시간을 잠깐 준 뒤 Enter (최상단 종목 선택)
    time.sleep(1.5)
    search_input.send_keys(Keys.ENTER)
    log(f"'{company_name}' 검색 후 Enter (검색 결과 최상단 종목 선택)")


def get_stock_code(driver, log=print):
    """검색 후 이동한 종목 페이지 주소에서 종목 코드를 꺼낸다"""
    # 검색이 끝나면 .../stocks/종목코드/order 로 이동 -> 주소가 바뀔 때까지 대기
    # 없는 회사명이면 이동하지 않으므로 TimeoutException 발생
    WebDriverWait(driver, 15).until(EC.url_contains('/order'))

    parts = driver.current_url.split('/')
    stock_code = parts[parts.index('stocks') + 1]
    log(f'종목 코드 확인 : {stock_code}')
    return stock_code


# ------------------------------------------------------------
# [추가] 실제종목명 추출 (F602)
# ------------------------------------------------------------
# 종목 페이지의 제목(<title>, og:title)은 보통 '삼성전자 - 토스증권' 처럼
# "종목명 + 구분자 + 사이트 이름" 형태 -> 구분자 앞부분이 종목명
TITLE_NOISE = re.compile(r'(토스증권|토스|주가|시세|차트|주식|커뮤니티|\(\w+\))')


def clean_title(title):
    """페이지 제목에서 사이트 이름·불필요한 단어를 떼고 종목명만 남긴다"""
    if not title:
        return ''
    first = re.split(r'\s[|\-–·:]\s|\|', title)[0]
    name = TITLE_NOISE.sub('', first)
    return ' '.join(name.split())


def get_stock_name(driver, fallback, main_title=''):
    """종목 페이지에서 실제 종목명을 찾는다 (못 찾으면 fallback)

    main_title : 메인 페이지 제목에서 뽑은 값. 제목이 아직 메인 페이지 그대로라면
                 종목명이 아니므로 사용하지 않는다
    """
    # 주소는 바뀌었어도 제목이 늦게 바뀌는 경우가 있어 잠깐 기다림
    try:
        WebDriverWait(driver, 5).until(
            lambda d: clean_title(d.title) and clean_title(d.title) != main_title
        )
    except TimeoutException:
        pass

    candidates = []
    try:
        og = driver.find_element(By.CSS_SELECTOR, "meta[property='og:title']")
        candidates.append(og.get_attribute('content'))
    except Exception:
        pass
    candidates.append(driver.title)

    for title in candidates:
        name = clean_title(title)
        if name and name != main_title:
            return name
    return fallback


def open_community(driver, stock_code, log=print):
    """종목 코드로 커뮤니티 페이지 주소를 만들어 바로 이동한다"""
    driver.get(f'{MAIN_URL.rstrip("/")}/stocks/{stock_code}/community')
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#stock-content'))
        )
        log('커뮤니티 댓글 영역 로딩 완료')
    except TimeoutException:
        log('커뮤니티 영역을 10초 안에 찾지 못했습니다. 그대로 진행합니다.')


# 댓글 본문 선택자 : 클래스 이름이 아니라 "역할"을 나타내는 속성을 기준으로
COMMENT_SELECTOR = "span[style*='--fold-after-lines']"


def read_visible_comments(driver, comments, seen=None):
    """화면의 댓글을 모은다. 동일 문장이어도 서로 다른 게시물이면 유지한다.

    게시물 ID가 있는 경우 ID로 판별하고, 없는 경우 같은 화면의 등장 순서를
    사용한다. 타 화면에서 같은 문장·순서로 반복 등장하는 경우에는 구분이 어려우며,
    외부 사이트의 DOM 구조가 바뀌면 식별 방식을 보완해야 한다.
    """
    if seen is None:
        seen = set()
    visible_counts = {}
    for span in driver.find_elements(By.CSS_SELECTOR, COMMENT_SELECTOR):
        try:
            text = span.text.strip()
        except Exception:
            continue
        if not text:
            continue
        visible_counts[text] = visible_counts.get(text, 0) + 1
        marker = None
        try:
            marker = driver.execute_script("""
                const node = arguments[0].closest('[data-comment-id],[data-post-id],[data-article-id]');
                return node ? (node.getAttribute('data-comment-id') ||
                    node.getAttribute('data-post-id') || node.getAttribute('data-article-id')) : null;
            """, span)
        except Exception:
            pass
        key = ('id', str(marker)) if marker else ('text-ordinal', text, visible_counts[text])
        if key not in seen:
            seen.add(key)
            comments.append(text)


def find_scroll_container(driver):
    """댓글 목록을 감싼 내부 스크롤 영역을 찾는다 (없으면 None)"""
    try:
        return driver.find_element(
            By.CSS_SELECTOR, "div[data-id^='base-ui-'][data-id$='-viewport']"
        )
    except Exception:
        return None


def collect_comments(driver, limit=20, max_scroll=30, log=print):
    """스크롤을 반복하며 댓글을 최대 limit 개까지 모아 돌려준다"""
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, COMMENT_SELECTOR))
        )
    except TimeoutException:
        log('댓글을 찾지 못했습니다.')
        return []

    scroll_container = find_scroll_container(driver)
    comments = []
    seen = set()
    prev_count = -1
    stagnant_rounds = 0

    for scroll in range(max_scroll):
        read_visible_comments(driver, comments, seen)
        log(f'댓글 수집 중... 스크롤 {scroll + 1}회 -> 누적 {min(len(comments), limit)}/{limit}개')

        if len(comments) >= limit or scroll_container is None:
            break

        # 스크롤해도 5번 연속 늘지 않으면 더 이상 댓글이 없다고 판단
        if len(comments) == prev_count:
            stagnant_rounds += 1
            if stagnant_rounds >= 5:
                break
        else:
            stagnant_rounds = 0
        prev_count = len(comments)

        try:
            scroll_container.click()
            scroll_container.send_keys(Keys.END)
        except Exception:
            # 클릭이 막히면 자바스크립트로 스크롤
            driver.execute_script(
                'arguments[0].scrollTop = arguments[0].scrollHeight;', scroll_container
            )
        time.sleep(1.5)  # 새 댓글을 불러올 시간

    return comments[:limit]


# ------------------------------------------------------------
# 외부에서 사용할 함수 : 회사명 => 수집 결과 딕셔너리
# ------------------------------------------------------------
def make_result(status, company_name, message='', stock_name='', stock_code='', comments=None, market_snapshot=None):
    return {
        'status': status,
        'message': message,
        'stock_name': stock_name,
        'stock_code': stock_code,
        'comments': comments or [],
        'market_snapshot': market_snapshot or {},
    }


def fetch_comments(company_name, limit=20, headless=True, log=print):
    """회사명으로 커뮤니티 댓글을 최대 limit 개 수집해 결과 딕셔너리로 돌려준다"""
    try:
        driver = get_driver(headless)
    except WebDriverException as e:
        return make_result(
            STATUS_ERROR, company_name,
            f'크롬 브라우저를 실행하지 못했습니다. ({e.msg or e.__class__.__name__})',
        )

    try:
        open_main(driver, log)
        main_title = clean_title(driver.title)  # 종목명 추출 시 비교용
        # 토스증권 홈페이지 시장정보를 댓글 검색과 동일한 크롬 브라우저에서 수집한다.
        # 외부 사이트 화면 변경/수집 실패가 댓글 수집을 중단하지 않도록 격리한다.
        snapshot = {}
        try:
            from market.services import capture_with_driver
            close_popups(driver)
            snapshot = capture_with_driver(driver, log=log)
        except Exception as exc:
            log(f'시장정보 수집을 건너뜁니다 ({exc.__class__.__name__}). 댓글 수집은 계속합니다.')
        search_company(driver, company_name, log)
        try:
            stock_code = get_stock_code(driver, log)
        except TimeoutException:
            # 없는 회사명이면 종목 페이지로 이동하지 못해 시간 초과 발생
            return make_result(
                STATUS_NO_COMPANY, company_name,
                f"'{company_name}' 에 해당하는 회사를 찾지 못했습니다. 회사명을 다시 확인해 주세요.",
                market_snapshot=snapshot,
            )

        stock_name = get_stock_name(driver, fallback=company_name, main_title=main_title)
        log(f'실제 종목명 : {stock_name}')

        open_community(driver, stock_code, log)
        comments = collect_comments(driver, limit=limit, log=log)
        if not comments:
            return make_result(
                STATUS_NO_COMMENTS, company_name,
                f"'{stock_name}' 커뮤니티에 수집할 댓글이 없습니다.",
                stock_name, stock_code, market_snapshot=snapshot,
            )
        return make_result(STATUS_OK, company_name, '', stock_name, stock_code, comments, market_snapshot=snapshot)

    except TimeoutException:
        return make_result(
            STATUS_ERROR, company_name,
            '토스증권 페이지가 제때 열리지 않았습니다. 잠시 후 다시 시도해 주세요.',
        )
    except WebDriverException as e:
        return make_result(
            STATUS_ERROR, company_name,
            f'크롤링 중 브라우저 오류가 발생했습니다. ({e.msg or e.__class__.__name__})',
        )
    finally:
        driver.quit()


# ------------------------------------------------------------
# 샘플 모드 : 토스증권 접속 없이 data/comments_sample.json 사용
# ------------------------------------------------------------
def fetch_sample_comments(company_name, sample_path, limit=20, log=print):
    """샘플 파일의 댓글로 수집 결과를 흉내 낸다 (개발·테스트용)"""
    with open(sample_path, encoding='utf-8') as f:
        sample = json.load(f)
    log(f'[샘플 모드] {sample_path.name} 에서 댓글을 불러옵니다')
    from market.services import demo_snapshot
    return make_result(
        STATUS_OK, company_name, '',
        stock_name=sample.get('company', company_name),
        stock_code='SAMPLE',
        comments=sample['comments'][:limit],
        market_snapshot=demo_snapshot(),
    )


if __name__ == '__main__':
    print(fetch_comments('삼성', limit=5, headless=False))
