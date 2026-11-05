"""Load 100 sourced catalog entries from bundled SQLite into the active Django database.

Data source details: data/CATALOG_SOURCES.md. Does not require external API access.
"""
from pathlib import Path
import sqlite3
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from books.models import Book, Category

CATEGORY_NAMES = ['소설/시/희곡','경제/경영','자기계발','인문/교양','취미/실용','어린이/청소년','과학']

class Command(BaseCommand):
    help = 'Bundled 100 real catalog books into the Django database. Safe to rerun.'
    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--dry-run', action='store_true')
    def handle(self, *args, **options):
        limit = options['limit']
        if not 1 <= limit <= 100:
            raise CommandError('--limit must be between 1 and 100')
        catalog = Path(settings.BASE_DIR) / 'data' / 'catalog_100.sqlite3'
        if not catalog.is_file():
            raise CommandError(f'Missing bundled catalog: {catalog}')
        with sqlite3.connect(f'file:{catalog}?mode=ro', uri=True) as connection:
            connection.row_factory = sqlite3.Row
            records = [dict(x) for x in connection.execute('SELECT * FROM catalog_books ORDER BY id LIMIT ?', (limit,))]
        if options['dry_run']:
            self.stdout.write(f'Dry run: {len(records)} bundled records available; nothing saved.')
            return
        with transaction.atomic():
            user_model=get_user_model()
            user, made=user_model.objects.get_or_create(username='thread_catalog', defaults={'email':''})
            if made:
                user.set_unusable_password(); user.save(update_fields=['password'])
            for name in CATEGORY_NAMES:
                Category.objects.get_or_create(name=name)
            category = Category.objects.get(name='소설/시/희곡')
            created=updated=skipped=0
            for record in records:
                isbn=(record.get('isbn13') or '').strip()
                book = (Book.objects.filter(aladin_isbn13=isbn).first() if isbn else None)
                if book is None:
                    book=Book.objects.filter(title=record['title'],author=record['author']).first()
                if book:
                    skipped+=1
                    continue
                Book.objects.create(
                    user=user,title=record['title'][:200],author=record['author'][:120],
                    description=record['description'] or '도서 소개 미제공',rating=3,
                    category=category if record['source']=='goodbooks_10k_public_sample' else None,
                    aladin_isbn13=isbn if len(isbn)==13 and isbn.isdigit() else '',
                    aladin_cover_url=(record.get('cover') or '')[:500],
                    aladin_publisher=(record.get('publisher') or '')[:200],
                    aladin_pub_date=(record.get('pub_date') or '')[:30],
                )
                created+=1
        self.stdout.write(self.style.SUCCESS(f'Catalog sync done: created={created}, existing={skipped}, supplied={len(records)}'))
