"""알라딘 Open API 로 도서 목록 가져오기 (2회차에서 배운 API 활용)

상품 리스트 API : https://www.aladin.co.kr/ttb/api/ItemList.aspx
    QueryType
        ItemNewSpecial : 주목할 만한 신간 (기본값)
        ItemNewAll     : 신간 전체
        Bestseller     : 베스트셀러
        BlogBest       : 블로거 베스트셀러

키(TTBKEY)는 코드에 쓰지 않고 .env 에서 읽음 (settings.ALADIN_TTBKEY)
"""

import html
import re

from django.conf import settings

try:
    import requests
except ImportError:
    requests = None

ITEM_LIST_URL = 'https://www.aladin.co.kr/ttb/api/ItemList.aspx'
QUERY_TYPES = ['ItemNewSpecial', 'ItemNewAll', 'Bestseller', 'BlogBest']
PAGE_SIZE = 50   # 한 번에 받을 개수 (알라딘 ItemList 최대 50)
MAX_PAGES = 10   # 무한 반복 방지
TIMEOUT = 10


class AladinError(Exception):
    """알라딘 API 호출 실패 (화면 · 터미널에 보여 줄 안내 문구를 담음)"""


def clean_text(text):
    """HTML 태그(<br/> 등)를 지운 뒤 엔티티(&lt; 등)를 글자로 바꾸고 앞뒤 공백 정리

    ※ 순서 주의 : 알라딘은 책 제목을 &lt;자전거여행&gt; 처럼 보내므로,
      엔티티를 먼저 바꾸면 <자전거여행> 이 태그로 오인되어 지워짐
    """
    text = re.sub(r'<[^>]+>', '', text or '')
    return html.unescape(text).strip()


def clean_title(title):
    """'여행의 이유 (개정증보판) - 부제' -> '여행의 이유'  (부제 · 판 표기 제거)"""
    title = clean_text(title).split(' - ')[0].strip()
    title = re.sub(r'\s*\((?:[^()]*(?:판|리커버|에디션|양장))\)\s*$', '', title).strip()
    return title[:100]


def clean_author(author):
    """'한강 (지은이), 홍길동 (옮긴이)' -> '한강'  (대표 저자 한 명)"""
    first = clean_text(author).split(',')[0]
    return re.sub(r'\s*\(.*?\)', '', first).strip()[:100]


def to_book_data(item):
    """알라딘 item 하나를 Book 모델 필드 dict 로 변환. 쓸 수 없는 항목이면 None"""
    title = clean_title(item.get('title'))
    author = clean_author(item.get('author'))
    description = clean_text(item.get('description'))
    if item.get('adult') or not (title and author and description):
        return None  # 성인 도서 · 설명이 없는 도서는 제외 (Book.description 은 필수)
    try:
        rank = int(item.get('customerReviewRank') or 0)
    except (TypeError, ValueError):
        rank = 0
    return {
        'title': title,
        'author': author,
        'description': description,
        'customer_review_rank': min(max(rank, 0), 10),  # 0 ~ 10 (신간은 리뷰가 없으면 0)
    }


def fetch_items(query_type='ItemNewSpecial', page=1, category_id=0):
    """ItemList API 한 페이지를 호출해 item 리스트를 돌려줌"""
    if requests is None:
        raise AladinError('requests 가 설치되지 않았습니다. (pip install -r requirements.txt)')
    if not settings.ALADIN_TTBKEY:
        raise AladinError('TTBKEY 가 설정되지 않았습니다. (.env 에 TTBKEY=발급받은키 추가)')
    params = {
        'ttbkey': settings.ALADIN_TTBKEY,
        'QueryType': query_type,
        'MaxResults': PAGE_SIZE,
        'start': page,
        'SearchTarget': 'Book',
        'CategoryId': category_id,  # 0 = 전체
        'output': 'js',             # JSON 형식
        'Version': '20131101',
    }
    try:
        response = requests.get(ITEM_LIST_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise AladinError(f'알라딘 API 호출에 실패했습니다. ({type(error).__name__})') from error
    if 'errorCode' in data:  # 잘못된 키 등 : {"errorCode": 2, "errorMessage": "..."}
        raise AladinError(f"알라딘 API 오류 : {data.get('errorMessage', data['errorCode'])}")
    return data.get('item', [])


def fetch_books(count=100, query_type='ItemNewSpecial', category_id=0):
    """쓸 수 있는 도서를 count 권 모을 때까지 페이지를 넘기며 가져옴 → Book 필드 dict 리스트"""
    books, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        items = fetch_items(query_type, page, category_id)
        if not items:
            break
        for item in items:
            data = to_book_data(item)
            if not data:
                continue
            key = (data['title'], data['author'])
            if key in seen:  # 같은 책의 다른 판본 등 중복 제외
                continue
            seen.add(key)
            books.append(data)
            if len(books) >= count:
                return books
    return books
