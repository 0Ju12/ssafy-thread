"""생성형 AI(GMS Responses API) + 위키피디아 API 활용 기능

F417 심화 : 작가 정보 생성
    ① search_wikipedia(author)     위키피디아에서 작가 문서를 찾아 요약 · 사진 주소를 받음
    ② ask_llm(...)                 사용자 입력 + 위키 요약을 GMS API 에 보내 JSON 으로 작가 정보 · 대표작 요청
    ③ generate_author_profile(...) ① + ② 를 묶어 Book 에 저장할 dict 를 돌려줌

추가 기능
    analyze_book(book)             AI 도서 분석 : 한 줄 요약 · 키워드 · 추천 독자 · 감상 포인트
    recommend_books(user, books)   AI 맞춤 도서 추천 : 회원의 관심 장르 · 독서 습관으로 등록된 도서 중 추천
    ping()                         연결 확인 : "Hello, World!" 를 보내 응답 받기 (python manage.py gms_ping)

GMS 호출은 모두 call_llm() 한 곳을 거침 = POST {GMS_BASE_URL}/responses (Responses API)
키(GMS_KEY) · 모델(GMS_MODEL)은 코드에 쓰지 않고 .env 에서 읽음 (settings.py 참고)
"""

import json
import logging
import re

from django.conf import settings

# requests 는 위키피디아 검색에만 필요 => 설치되지 않아도 서버는 실행되도록 처리
try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

WIKI_API_URLS = [
    'https://ko.wikipedia.org/w/api.php',  # 한국어 위키 먼저
    'https://en.wikipedia.org/w/api.php',  # 없으면 영어 위키
]
WIKI_TIMEOUT = 10
LLM_TIMEOUT = 60
MAX_WIKI_TEXT = 2000  # 프롬프트에 넣을 위키 본문 최대 길이
MAX_WORKS = 5


class AIError(Exception):
    """AI 기능 실패 (화면에 보여 줄 안내 문구를 담음)"""


# 기존 이름 유지 (작가 정보 생성 실패)
AuthorInfoError = AIError


# ---------------------------------------------------------------------------
# ① 위키피디아
# ---------------------------------------------------------------------------
def _wiki_headers():
    # 위키피디아 API 는 User-Agent 로 요청자를 구분함 (연락처가 있으면 요청 한도가 넉넉해짐)
    contact = settings.WIKI_CONTACT.strip()
    agent = f'ThRead-SSAFY/1.0 ({contact}) python-requests' if contact else 'ThRead-SSAFY/1.0 python-requests'
    return {'User-Agent': agent}


def _wiki_get(api_url, params):
    response = requests.get(
        api_url,
        params={**params, 'format': 'json', 'formatversion': 2},
        headers=_wiki_headers(),
        timeout=WIKI_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def search_wikipedia(author):
    """작가 이름으로 위키 문서를 찾아 {'title', 'url', 'extract', 'image'} 를 돌려줌. 못 찾으면 None"""
    if requests is None:
        logger.warning('requests 가 설치되지 않아 위키피디아 검색을 건너뜁니다.')
        return None
    for api_url in WIKI_API_URLS:
        try:
            found = _wiki_get(api_url, {
                'action': 'query',
                'list': 'search',
                'srsearch': author,
                'srlimit': 1,
            })
            results = found.get('query', {}).get('search', [])
            if not results:
                continue

            title = results[0]['title']
            data = _wiki_get(api_url, {
                'action': 'query',
                'titles': title,
                'prop': 'extracts|pageimages|info',
                'exintro': 1,         # 문서 첫 단락(요약)만
                'explaintext': 1,     # 태그 없는 본문
                'piprop': 'thumbnail',
                'pithumbsize': 400,   # 프로필 사진 크기
                'inprop': 'url',
                'redirects': 1,
            })
            page = data['query']['pages'][0]
            if page.get('missing'):
                continue
            return {
                'title': page.get('title', title),
                'url': page.get('fullurl', ''),
                'extract': page.get('extract', '')[:MAX_WIKI_TEXT],
                'image': page.get('thumbnail', {}).get('source', ''),
            }
        except (requests.RequestException, KeyError, ValueError, IndexError) as error:
            # 위키 검색이 실패해도 AI 생성은 계속 진행 (사진 · 참고 정보만 빠짐)
            logger.warning('위키피디아 검색 실패 (%s): %s', api_url, error)
    return None


# ---------------------------------------------------------------------------
# ② 생성형 AI (GMS)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    '너는 도서 커뮤니티 서비스의 작가 정보 도우미다. '
    '반드시 JSON 객체 하나만 응답하고, 그 밖의 설명 문장은 쓰지 않는다.'
)

USER_PROMPT_TEMPLATE = """다음 정보를 바탕으로 작가 정보와 대표작 목록을 만들어 줘.

[사용자 입력]
- 저자: {author}
- 도서 제목: {title}
- 도서 설명: {description}

[위키피디아 검색 결과]
{wiki}

[응답 형식] 아래 키만 가진 JSON 객체
{{
  "author_info": "작가를 소개하는 한국어 2~3문장 (출생·국적·대표 경력 위주)",
  "author_works": ["대표작1", "대표작2", "..."]
}}

[규칙]
- 위키피디아 검색 결과가 있으면 그 내용을 우선으로 사용한다.
- author_works 는 최대 {max_works}개, 작품 제목만 쓴다.
- 확실하지 않은 정보는 지어내지 말고, 모르면 author_info 는 빈 문자열, author_works 는 빈 리스트로 둔다.
"""


def _get_client():
    # openai 라이브러리는 함수 안에서 import (라이브러리가 없어도 나머지 기능은 동작하도록)
    from openai import OpenAI

    return OpenAI(api_key=settings.GMS_KEY, base_url=settings.GMS_BASE_URL, timeout=LLM_TIMEOUT)


def _check_key():
    if not settings.GMS_KEY:
        raise AIError('GMS_KEY 가 설정되지 않아 AI 기능을 사용할 수 없습니다. (.env 확인)')


def call_llm(input_data, instructions=None, want_json=False):
    """GMS Responses API 호출 : POST {GMS_BASE_URL}/responses

    curl 예시와 같은 요청
        {"model": "<GMS_MODEL>", "input": "Hello, World!"}
    want_json=True 이면 JSON 객체로만 응답하도록 요청하고, 결과를 dict 로 돌려줌
    """
    params = {'model': settings.GMS_MODEL, 'input': input_data}
    if instructions:
        params['instructions'] = instructions  # system 역할 (페르소나 · 규칙)
    if want_json:
        params['text'] = {'format': {'type': 'json_object'}}  # JSON 형태로만 응답
    if settings.GMS_MODEL.startswith('gpt-5'):
        # gpt-5 계열 전용 옵션 : 추론 강도를 낮춰 응답 속도를 높임 (minimal / low / medium / high)
        params['reasoning'] = {'effort': 'low'}

    response = _get_client().responses.create(**params)

    # 답변이 토큰 한도 등으로 중간에 잘렸으면 내용이 깨져 있으므로 실패로 처리
    if getattr(response, 'status', None) == 'incomplete':
        raise ValueError('응답이 중간에 잘렸습니다 (status=incomplete)')
    usage = getattr(response, 'usage', None)
    if usage is not None:
        logger.info('[GMS] model=%s 토큰 입력 %s / 출력 %s',
                    settings.GMS_MODEL, getattr(usage, 'input_tokens', '?'), getattr(usage, 'output_tokens', '?'))

    text = response.output_text
    return parse_llm_json(text) if want_json else text


def _run(feature_name, func, *args):
    """AI 호출을 감싸서, 실패하면 화면에 보여 줄 AIError 로 바꿈"""
    _check_key()
    try:
        return func(*args)
    except AIError:
        raise
    except Exception as error:  # 네트워크 · 인증 · 모델 이름 · JSON 파싱 오류 등
        logger.exception('%s 실패', feature_name)
        raise AIError(f'{feature_name}에 실패했습니다. ({type(error).__name__})') from error


def ping():
    """연결 확인 : curl 예시처럼 "Hello, World!" 를 보내고 응답 문자열을 돌려줌"""
    return _run('GMS 연결 확인', call_llm, 'Hello, World!')


def parse_llm_json(text):
    """LLM 응답 문자열에서 JSON 객체를 꺼냄 (```json ... ``` 으로 감싸서 오는 경우도 처리)"""
    text = (text or '').strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group())


def ask_llm(author, title, description, wiki):
    """GMS API(gpt-5-nano)에 작가 정보를 JSON 으로 요청하고 {'author_info', 'author_works'} 를 돌려줌"""
    wiki_text = (
        f"문서 제목: {wiki['title']}\n요약: {wiki['extract']}" if wiki and wiki.get('extract')
        else '검색 결과 없음'
    )
    prompt = USER_PROMPT_TEMPLATE.format(
        author=author,
        title=title or '-',
        description=(description or '-')[:500],
        wiki=wiki_text,
        max_works=MAX_WORKS,
    )

    data = call_llm(prompt, instructions=SYSTEM_PROMPT, want_json=True)

    info = data.get('author_info', '')
    works = data.get('author_works', [])
    if isinstance(works, str):
        works = [w.strip() for w in works.split(',')]
    works = [str(w).strip() for w in works if str(w).strip()][:MAX_WORKS]
    return {'author_info': str(info).strip(), 'author_works': works}


# ---------------------------------------------------------------------------
# ③ 묶어서 사용
# ---------------------------------------------------------------------------
def generate_author_profile(author, title='', description=''):
    """Book 에 저장할 {'author_info', 'author_works', 'author_image'} 를 돌려줌

    실패하면 AuthorInfoError 를 발생시킴 (뷰에서 잡아서 경고 메시지로 보여 줌)
    """
    if not settings.GMS_KEY:
        raise AIError('GMS_KEY 가 설정되지 않아 작가 정보를 생성하지 않았습니다. (.env 확인)')

    wiki = search_wikipedia(author)
    result = _run('작가 정보 생성', ask_llm, author, title, description, wiki)

    return {
        'author_info': result['author_info'],
        'author_works': ', '.join(result['author_works']),
        'author_image': (wiki or {}).get('image', ''),
    }


# ---------------------------------------------------------------------------
# 추가 기능 ① AI 도서 분석
# ---------------------------------------------------------------------------
ANALYSIS_INSTRUCTIONS = (
    '너는 도서 커뮤니티 ThRead 의 도서 분석가다. 주어진 도서 정보만 근거로 분석하고, '
    '모르는 사실은 지어내지 않는다. 반드시 JSON 객체 하나만 한국어로 응답한다.'
)

ANALYSIS_PROMPT = """다음 도서를 분석해 줘.

- 제목: {title}
- 저자: {author}
- 회원 리뷰 평점: {rank} / 10
- 설명: {description}

[응답 형식] 아래 키만 가진 JSON 객체
{{
  "summary": "이 책을 한 문장으로 소개 (40자 내외)",
  "keywords": ["핵심 키워드 3~5개"],
  "target_readers": "이 책을 추천하고 싶은 독자 (한 문장)",
  "reading_points": ["읽을 때 주목할 감상 포인트 2~3개 (각 한 문장)"]
}}
"""


def _clean_list(value, limit):
    if isinstance(value, str):
        value = [v.strip() for v in value.split(',')]
    return [str(v).strip() for v in (value or []) if str(v).strip()][:limit]


def _analyze(book):
    data = call_llm(
        ANALYSIS_PROMPT.format(
            title=book.title, author=book.author,
            rank=book.customer_review_rank, description=book.description[:1000],
        ),
        instructions=ANALYSIS_INSTRUCTIONS,
        want_json=True,
    )
    result = {
        'summary': str(data.get('summary', '')).strip(),
        'keywords': _clean_list(data.get('keywords'), 5),
        'target_readers': str(data.get('target_readers', '')).strip(),
        'reading_points': _clean_list(data.get('reading_points'), 3),
    }
    # 형식이 맞지 않는 응답(빈 결과)은 저장하지 않고 실패로 처리
    if not (result['summary'] or result['keywords']):
        raise AIError('AI 도서 분석 결과가 비어 있습니다. 잠시 뒤 다시 시도해 주세요.')
    return result


def analyze_book(book):
    """도서 정보로 {'summary', 'keywords', 'target_readers', 'reading_points'} 를 돌려줌"""
    return _run('AI 도서 분석', _analyze, book)


# ---------------------------------------------------------------------------
# 추가 기능 ② AI 맞춤 도서 추천
# ---------------------------------------------------------------------------
RECOMMEND_INSTRUCTIONS = (
    '너는 도서 커뮤니티 ThRead 의 도서 큐레이터다. 반드시 [도서 목록] 안에 있는 도서만 추천하고, '
    '목록에 없는 책은 절대 만들어 내지 않는다. 반드시 JSON 객체 하나만 한국어로 응답한다.'
)

RECOMMEND_PROMPT = """회원 정보를 보고 [도서 목록]에서 이 회원에게 맞는 책을 최대 {count}권 골라 줘.

[회원 정보]
- 성별: {gender}
- 나이: {age}
- 주간 평균 독서 시간: {weekly}
- 연간 독서량: {annual}
- 관심 장르: {genres}

[도서 목록] (id | 제목 | 저자 | 평점 | 설명 일부)
{book_lines}

[응답 형식] 아래 키만 가진 JSON 객체
{{
  "recommendations": [
    {{"id": 도서 id 숫자, "reason": "이 회원에게 추천하는 이유 (한 문장)"}}
  ]
}}
"""


def _recommend(user, books, count):
    by_id = {book.pk: book for book in books}
    book_lines = '\n'.join(
        f'{b.pk} | {b.title} | {b.author} | {b.customer_review_rank} | {b.description[:80]}'
        for b in books
    )
    data = call_llm(
        RECOMMEND_PROMPT.format(
            count=count,
            gender=user.get_gender_display() or '미입력',
            age=f'{user.age}세' if user.age is not None else '미입력',
            weekly=f'{user.weekly_avg_reading_time}시간' if user.weekly_avg_reading_time is not None else '미입력',
            annual=f'{user.annual_reading_amount}권' if user.annual_reading_amount is not None else '미입력',
            genres=user.get_interested_genres_display() or '미입력',
            book_lines=book_lines,
        ),
        instructions=RECOMMEND_INSTRUCTIONS,
        want_json=True,
    )

    results, seen = [], set()
    for item in data.get('recommendations', []):
        try:
            book_id = int(item.get('id'))
        except (TypeError, ValueError, AttributeError):
            continue
        # 목록에 없는 id(AI 가 지어낸 책) · 중복은 버림
        if book_id in by_id and book_id not in seen:
            seen.add(book_id)
            results.append({
                'id': book_id,
                'title': by_id[book_id].title,
                'author': by_id[book_id].author,
                'reason': str(item.get('reason', '')).strip(),
            })
    if not results:
        raise AIError('추천할 도서를 찾지 못했습니다. 잠시 뒤 다시 시도해 주세요.')
    return results[:count]


def recommend_books(user, books, count=3):
    """회원 정보로 등록된 도서 중 최대 count 권을 골라 [{'id', 'title', 'author', 'reason'}] 로 돌려줌"""
    books = list(books)
    if not books:
        raise AIError('등록된 도서가 없어 추천할 수 없습니다.')
    return _run('AI 맞춤 도서 추천', _recommend, user, books, count)
