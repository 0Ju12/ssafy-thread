"""Fill ONLY missing descriptions for existing Django Book rows via GMS.

Examples:
    python manage.py generate_book_descriptions --dry-run
    python manage.py generate_book_descriptions --limit 100
"""
import time
from django.core.management.base import BaseCommand, CommandError
from books.models import Book
from books.description_ai import generate_description, needs_description


class Command(BaseCommand):
    help = 'GMS로 도서 소개가 없는 항목만 안내문 생성 (기존 소개 보존, AI 표시).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100, help='이번 실행에 처리할 최대 도서 수')
        parser.add_argument('--dry-run', action='store_true', help='변경 대상만 출력하고 API 호출/저장은 하지 않음')
        parser.add_argument('--delay', type=float, default=0.5, help='호출 간 대기 시간(초)')
        parser.add_argument('--model', default=None, help='선택적 GMS 모델 이름')

    def handle(self, *args, **options):
        limit = options['limit']
        if limit < 1 or options['delay'] < 0:
            raise CommandError('limit는 1 이상, delay는 0 이상이어야 합니다.')
        # Python-side filtering ensures all known previous placeholders are recognized.
        missing = [book for book in Book.objects.order_by('pk').iterator() if needs_description(book.description)]
        targets = missing[:limit]
        self.stdout.write(f'전체 {Book.objects.count()}권 / 소개 누락 {len(missing)}권 / 처리 대상 {len(targets)}권')
        if options['dry_run']:
            for book in targets:
                self.stdout.write(f'  [{book.pk}] {book.title[:60]}')
            return
        if not targets:
            self.stdout.write(self.style.SUCCESS('소개가 누락된 도서가 없습니다.'))
            return
        succeeded = failed = 0
        for index, book in enumerate(targets, 1):
            try:
                text = generate_description(book, model=options['model'])
                # Guard in case another process edited this record during the API call.
                actual = Book.objects.get(pk=book.pk)
                if not needs_description(actual.description):
                    self.stdout.write(f'[{index}/{len(targets)}] 건너뜀: 이미 소개가 등록됨 - {book.title}')
                    continue
                actual.description = text
                actual.save(update_fields=['description'])
                succeeded += 1
                self.stdout.write(self.style.SUCCESS(f'[{index}/{len(targets)}] 저장: {book.title}'))
            except (ValueError, OSError, Book.DoesNotExist) as exc:
                failed += 1
                self.stderr.write(self.style.WARNING(f'[{index}/{len(targets)}] 실패: {book.title} / {exc}'))
                if '설정되지 않았습니다' in str(exc):
                    break
            if index < len(targets) and options['delay']:
                time.sleep(options['delay'])
        self.stdout.write(f'처리 완료: 저장 {succeeded}건 / 실패 {failed}건 / 기존 소개 유지')
        if failed:
            self.stderr.write('실패한 책은 설명을 그대로 유지합니다. 설정을 수정한 뒤 다시 실행하면 해당 책만 재시도합니다.')
