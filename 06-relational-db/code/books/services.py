"""Optional external AI integration. Never blocks basic CRUD on missing API credentials."""
import json,os,urllib.request,urllib.parse
from django.core.files.base import ContentFile
from django.conf import settings
import logging
logger=logging.getLogger(__name__)

def _openai(endpoint,payload):
    key=os.getenv('OPENAI_API_KEY')
    if not key:return None
    request=urllib.request.Request('https://api.openai.com/v1/'+endpoint,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=25) as response:return json.load(response)

def enrich_author(book):
    """Wikipedia 검색은 선택 사항. 검색 실패 시에도 GPT 정보 생성 시도."""
    source = ''
    photo_url = ''
    try:
        query = urllib.parse.urlencode({
            'action': 'query', 'generator': 'search', 'gsrsearch': book.author,
            'gsrlimit': 1, 'prop': 'extracts|pageimages', 'exintro': 1,
            'explaintext': 1, 'pithumbsize': 300, 'format': 'json',
        })
        wiki_request = urllib.request.Request(
            'https://ko.wikipedia.org/w/api.php?' + query,
            headers={'User-Agent': 'ThRead-SSAFY-Project/1.0 (educational app)'},
        )
        with urllib.request.urlopen(wiki_request, timeout=8) as response:
            pages = json.load(response).get('query', {}).get('pages', {})
        page = next(iter(pages.values()), {})
        source = page.get('extract', '')[:1500]
        photo_url = page.get('thumbnail', {}).get('source', '')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning('Wikipedia author search failed: %s', exc)

    try:
        answer = _openai('chat/completions', {
            'model': os.getenv('OPENAI_TEXT_MODEL', 'gpt-5-nano'),
            'messages': [
                {'role': 'system', 'content': '작가 정보를 JSON {"info":"...","works":"..."}로 반환. 검증되지 않은 사실은 추측하지 말 것.'},
                {'role': 'user', 'content': f'작가 이름: {book.author}; 위키피디아 참고자료: {source or "자료 없음"}'},
            ],
            'response_format': {'type': 'json_object'},
        })
        if answer:
            data = json.loads(answer['choices'][0]['message']['content'])
            book.author_info = str(data.get('info') or source)
            book.author_works = str(data.get('works') or '')
        else:
            book.author_info = source
        book.author_photo_url = photo_url
        book.save(update_fields=['author_info', 'author_works', 'author_photo_url'])
        return bool(book.author_info or book.author_works)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning('AI author enrichment failed: %s', exc)
        if source or photo_url:
            book.author_info = source
            book.author_photo_url = photo_url
            book.save(update_fields=['author_info', 'author_photo_url'])
        return bool(source)

def generate_cover(thread):
    try:
        result=_openai('chat/completions',{'model':os.getenv('OPENAI_TEXT_MODEL','gpt-5-nano'),'messages':[{'role':'user','content':f'다음 독서 감상에서 감정 키워드 5개를 쉼표로 구분해 추출: {thread.book.title}, {thread.book.author}, {thread.content[:1500]}'}]})
        if not result:return False
        keywords=result['choices'][0]['message']['content'][:300]
        image=_openai('images/generations',{'model':os.getenv('OPENAI_IMAGE_MODEL','dall-e-3'),'prompt':f'Original editorial book review cover art, no text. Book: {thread.book.title}; author: {thread.book.author}; emotions: {keywords}','size':'1024x1024','response_format':'url'})
        url=image['data'][0]['url']
        with urllib.request.urlopen(url,timeout=25) as response:thread.cover_image.save(f'thread_{thread.pk}.png',ContentFile(response.read()),save=True)
        return True
    except (OSError,ValueError,KeyError,TypeError) as exc:
        logger.warning("AI integration failed: %s",exc)
        return False
