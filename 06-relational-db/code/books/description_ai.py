"""Optional GMS-generated book introductions; no fabricated publisher blurbs.

Only bibliographic metadata is supplied. Never claim to know a book's plot when
no authoritative description is provided. All generated copy is disclosed.
"""
import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

MISSING_DESCRIPTIONS = frozenset({
    '',
    '도서 소개는 출처 데이터셋에 포함되지 않았습니다.',
    '제공된 도서 데이터에 소개가 없습니다.',
    '도서 소개 미제공',
    '도서 소개를 입력해 주세요.',
})
AI_PREFIX = '[AI 작성 도서 안내 · 실제 책 내용과 다를 수 있습니다]'


def needs_description(value):
    return (value or '').strip() in MISSING_DESCRIPTIONS


def generate_description(book, *, api_key=None, base_url=None, model=None, timeout=35):
    """Return clearly marked Korean promotional text, or raise ValueError.

    GPT output is *not* treated as a sourced book summary. No API key or credentials
    are logged or embedded in source files.
    """
    key = api_key if api_key is not None else (os.getenv('GMS_KEY') or os.getenv('OPENAI_API_KEY'))
    if not key:
        raise ValueError('GMS_KEY 또는 OPENAI_API_KEY가 설정되지 않았습니다.')
    base = (base_url or os.getenv('GMS_BASE_URL') or 'https://gms.ssafy.io/gmsapi/api.openai.com/v1').rstrip('/')
    if not base.startswith('https://'):
        raise ValueError('보안을 위해 HTTPS API 주소만 허용합니다.')
    selected_model = model or os.getenv('GMS_MODEL') or os.getenv('MODEL') or 'gpt-6.1-sol'
    title = str(book.title).strip()
    author = str(book.author).strip()
    if not title or not author:
        raise ValueError('제목과 저자가 있어야 소개문을 생성할 수 있습니다.')
    system = (
        '당신은 한국어 도서 서비스의 편집자입니다. 확인 가능한 정보는 제공된 제목과 저자뿐입니다. '
        '줄거리, 등장인물, 시대적 배경, 목차, 수상, 작가 이력 등 미제공 사실을 지어내지 마세요. '
        '책의 제목이 떠올리게 하는 주제와 독자에게 던질 수 있는 질문만을 바탕으로 '
        '80~160자 분량의 자연스럽고 신중한 한국어 도서 안내 문장 2~3개를 작성하세요. '
        '실제 책을 읽거나 줄거리를 확인한 것처럼 주장하지 마세요. 제목과 저자명을 반복 나열하지 마세요. '
        '응답은 안내문 텍스트만 제공하세요.'
    )
    payload = {
        'model': selected_model,
        'input': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': f'도서 제목: {title}\n저자: {author}\n출판사: {getattr(book, "aladin_publisher", "") or "미제공"}'},
        ],
        'max_output_tokens': 350,
    }
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        f'{base}/responses', data=data, method='POST',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as exc:
        raise ValueError(f'GMS API 응답 오류 (HTTP {exc.code}). 키·모델·주소를 확인하세요.') from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise ValueError('GMS API에 연결할 수 없습니다. 네트워크 및 설정을 확인하세요.') from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError('GMS 응답을 해석할 수 없습니다.') from exc
    try:
        content = answer.get('output_text') or ''
        if not content:
            pieces = []
            for item in answer.get('output', []):
                for part in item.get('content', []):
                    if part.get('type') in ('output_text', 'text'):
                        pieces.append(part.get('text', ''))
            content = ' '.join(pieces)
        introduction = str(content).strip().strip('"').strip()
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError('GMS 응답에 소개문이 없습니다.') from exc
    if len(introduction) < 25 or len(introduction) > 700:
        raise ValueError('GMS가 생성한 소개문 길이가 적절하지 않습니다.')
    return f'{AI_PREFIX}\n{introduction}'
