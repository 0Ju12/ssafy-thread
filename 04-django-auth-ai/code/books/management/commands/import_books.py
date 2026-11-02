"""알라딘 API 로 최신 도서를 가져와 DB 에 저장 : python manage.py import_books

예시
    python manage.py import_books                       # 주목할 만한 신간 100권
    python manage.py import_books --count 50            # 50권만
    python manage.py import_books --type Bestseller     # 베스트셀러
    python manage.py import_books --dry-run             # 저장하지 않고 목록만 확인
    python manage.py import_books --save-fixture books/fixtures/aladin_books.json
                                                        # 저장 + fixture 파일로도 내보내기 (키 없는 사람도 loaddata 가능)
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from books.aladin import QUERY_TYPES, AladinError, fetch_books
from books.models import Book


class Command(BaseCommand):
    help = '알라딘 상품 리스트 API 로 최신 도서를 가져와 Book 으로 저장합니다.'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=100, help='가져올 도서 수 (기본 100)')
        parser.add_argument('--type', default='ItemNewSpecial', choices=QUERY_TYPES,
                            help='ItemNewSpecial(주목할 신간, 기본) / ItemNewAll / Bestseller / BlogBest')
        parser.add_argument('--category', type=int, default=0, help='알라딘 카테고리 ID (0 = 전체)')
        parser.add_argument('--dry-run', action='store_true', help='DB 에 저장하지 않고 목록만 출력')
        parser.add_argument('--save-fixture', metavar='PATH', help='가져온 도서를 fixture(JSON) 파일로도 저장')

    def handle(self, *args, **options):
        count = options['count']
        if count < 1:
            raise CommandError('--count 는 1 이상이어야 합니다.')

        self.stdout.write(f"알라딘 {options['type']} 에서 {count}권을 가져옵니다...")
        try:
            books = fetch_books(count, options['type'], options['category'])
        except AladinError as error:
            raise CommandError(str(error))

        if not books:
            raise CommandError('가져온 도서가 없습니다.')

        for n, data in enumerate(books, start=1):
            self.stdout.write(f"{n:3d}. {data['title']} | {data['author']} | 평점 {data['customer_review_rank']}")
        if len(books) < count:
            # 알라딘 리스트는 종류(QueryType)마다 제공하는 도서 수에 한도가 있음
            self.stdout.write(self.style.WARNING(
                f'요청한 {count}권 중 {len(books)}권만 가져왔습니다. '
                '더 필요하면 --type 이나 --category 를 바꿔 한 번 더 실행하세요. (중복 없이 추가됨)'
            ))            
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'--dry-run : {len(books)}권을 확인만 하고 저장하지 않았습니다.'))
            return

        created = updated = 0
        saved = []
        for data in books:
            # 같은 제목 + 저자의 도서가 이미 있으면 새로 만들지 않고 내용만 갱신 (여러 번 실행해도 중복 없음)
            book, is_new = Book.objects.update_or_create(
                title=data['title'], author=data['author'],
                defaults={'description': data['description'],
                          'customer_review_rank': data['customer_review_rank']},
            )
            created += is_new
            updated += not is_new
            saved.append(book)

        self.stdout.write(self.style.SUCCESS(f'저장 완료 : 새로 추가 {created}권, 갱신 {updated}권'))

        if options['save_fixture']:
            self._save_fixture(saved, Path(options['save_fixture']))

    def _save_fixture(self, books, path):
        now = timezone.now().isoformat()
        data = [
            {
                'model': 'books.book',
                # 기존 샘플(pk 1~24, 101~103)과 겹치지 않도록 1001 번부터
                'pk': 1000 + n,
                'fields': {
                    'title': b.title, 'description': b.description,
                    'customer_review_rank': b.customer_review_rank, 'author': b.author,
                    'author_info': '', 'author_works': '', 'author_image': '', 'ai_analysis': {},
                    'created_at': now, 'updated_at': now,
                },
            }
            for n, b in enumerate(books, start=1)
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'fixture 저장 : {path} ({len(data)}권)'))
