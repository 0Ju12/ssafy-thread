"""Import up to N genuine Aladin catalog records into Book.

The Aladin OpenAPI was discontinued 2026-10-30; --file is the recommended
way to import authentic previously exported JSON (never synthetic metadata).
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import requests
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from books.models import Book

API_URL = 'https://www.aladin.co.kr/ttb/api/ItemList.aspx'


def normalize_record(data):
    if not isinstance(data, dict):
        return None
    title = str(data.get('title') or '').strip()[:200]
    author = str(data.get('author') or '').strip()[:120]
    if not title or not author:
        return None
    raw_isbn = str(data.get('isbn13') or '').replace('-', '').strip()
    isbn = raw_isbn if len(raw_isbn) == 13 and raw_isbn.isdigit() else ''
    cover = str(data.get('cover') or data.get('aladin_cover_url') or '').strip()[:500]
    if cover and (urlsplit(cover).scheme not in ('https', 'http') or not urlsplit(cover).netloc):
        cover = ''
    return {
        'title': title, 'author': author,
        'description': str(data.get('description') or '도서 소개 정보가 제공되지 않았습니다.').strip(),
        'aladin_isbn13': isbn,
        'aladin_cover_url': cover,
        'aladin_publisher': str(data.get('publisher') or data.get('aladin_publisher') or '').strip()[:200],
        'aladin_pub_date': str(data.get('pubDate') or data.get('pub_date') or data.get('aladin_pub_date') or '').strip()[:30],
    }


def extract_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        value = payload.get('item', payload.get('books', []))
        if isinstance(value, list):
            return value
    raise ValueError('JSON에 item 또는 books 목록이 없습니다.')


class Command(BaseCommand):
    help = '알라딘에서 확보한 JSON 또는 기존 API로 최대 100권을 중복 없이 DB에 등록'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='알라딘 API의 과거 JSON 응답/목록 파일')
        parser.add_argument('--api', action='store_true', help='기존 알라딘 API 조회 시도(2026-10-30 서비스 종료)')
        parser.add_argument('--username', required=True, help='가져온 도서의 작성자로 지정할 기존 사용자')
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--rating', type=int, default=3, help='초기 표시 평점, 1~5 (임시값)')
        parser.add_argument('--query-type', choices=['Bestseller', 'ItemNewAll', 'ItemNewSpecial'], default='Bestseller')
        parser.add_argument('--dry-run', action='store_true', help='DB에 저장하지 않고 결과만 확인')

    def handle(self, *args, **options):
        if bool(options['file']) == bool(options['api']):
            raise CommandError('--file 또는 --api 중 하나만 지정하세요.')
        limit = options['limit']
        if not 1 <= limit <= 200:
            raise CommandError('--limit은 1~200 사이여야 합니다.')
        if not 1 <= options['rating'] <= 5:
            raise CommandError('--rating은 1~5 사이여야 합니다.')
        user = get_user_model().objects.filter(username=options['username']).first()
        if user is None:
            raise CommandError('지정한 사용자 계정이 없습니다. python manage.py createsuperuser 명령으로 먼저 생성하세요.')
        if options['file']:
            try:
                payload = json.loads(Path(options['file']).read_text(encoding='utf-8-sig'))
                items = extract_items(payload)
            except (OSError, UnicodeError, ValueError) as exc:
                raise CommandError(f'알라딘 JSON 파일을 읽지 못했습니다: {exc}') from exc
        else:
            key = os.getenv('ALADIN_TTBKEY', '').strip()
            if not key:
                raise CommandError('.env에 ALADIN_TTBKEY가 없습니다.')
            self.stdout.write(self.style.WARNING('주의: 알라딘 OpenAPI는 2026-10-30 종료 공지되었습니다. 기존 키가 있어도 실패할 수 있습니다.'))
            items = []
            for page in range(1, (limit + 49)//50 + 1):
                try:
                    response = requests.get(API_URL, params={
                        'ttbkey': key, 'QueryType': options['query_type'],
                        'SearchTarget': 'Book', 'MaxResults': min(50, limit-len(items)),
                        'start': page, 'Cover': 'Big', 'output': 'js', 'Version': '20131101',
                    }, timeout=12)
                    response.raise_for_status()
                    batch = extract_items(response.json())
                except (requests.RequestException, ValueError) as exc:
                    raise CommandError(f'알라딘 응답 실패 (페이지 {page}): 서비스 종료 여부를 확인해 주세요.') from exc
                if not batch:
                    break
                items.extend(batch)
                if len(items) >= limit:
                    break
        created = duplicate = invalid = 0
        seen = set()
        with transaction.atomic():
            for raw in items[:limit]:
                data = normalize_record(raw)
                if not data:
                    invalid += 1
                    continue
                identity = ('isbn', data['aladin_isbn13']) if data['aladin_isbn13'] else ('text', data['title'].casefold(), data['author'].casefold())
                if identity in seen:
                    duplicate += 1
                    continue
                seen.add(identity)
                if data['aladin_isbn13']:
                    exists = Book.objects.filter(aladin_isbn13=data['aladin_isbn13']).exists()
                else:
                    exists = Book.objects.filter(title=data['title'], author=data['author']).exists()
                if exists:
                    duplicate += 1
                    continue
                if not options['dry_run']:
                    Book.objects.create(user=user, rating=options['rating'], **data)
                created += 1
            if options['dry_run']:
                transaction.set_rollback(True)
        mode = '미리보기' if options['dry_run'] else '저장'
        self.stdout.write(self.style.SUCCESS(f'{mode}: 신규 {created}권, 중복 {duplicate}권, 누락 {invalid}권 (입력 {len(items)}건)'))
        if created < limit:
            self.stdout.write(self.style.WARNING(f'{limit}권 미달: 원본 수량·중복·필수 항목 누락을 확인하세요. 가짜 데이터를 생성하지 않습니다.'))
