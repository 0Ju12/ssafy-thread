import json
from pathlib import Path
from tempfile import TemporaryDirectory
from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from books.models import Book
from books.management.commands.import_aladin_books import normalize_record, extract_items


class AladinImportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='importer', password='SomePassword123!')

    def test_normalize_rejects_missing_book_fields(self):
        self.assertIsNone(normalize_record({'title': '책'}))
        self.assertEqual(normalize_record({'title': '책', 'author': '저자'})['title'], '책')

    def test_import_limit_and_idempotence(self):
        with TemporaryDirectory() as d:
            file = Path(d) / 'books.json'
            file.write_text(json.dumps({'item': [
                {'title': f'도서{i}', 'author': '작가', 'isbn13': f'{i:013d}', 'description': '설명'} for i in range(105)
            ]}, ensure_ascii=False), encoding='utf-8')
            call_command('import_aladin_books', file=str(file), username='importer', limit=100, stdout=StringIO())
            self.assertEqual(Book.objects.count(), 100)
            call_command('import_aladin_books', file=str(file), username='importer', limit=100, stdout=StringIO())
            self.assertEqual(Book.objects.count(), 100)
            call_command('import_aladin_books', file=str(file), username='importer', limit=100, stdout=StringIO())
            self.assertEqual(Book.objects.count(), 100)

    def test_dry_run_does_not_write(self):
        with TemporaryDirectory() as d:
            file = Path(d) / 'books.json'
            file.write_text('[{"title":"테스트","author":"작가"}]', encoding='utf-8')
            call_command('import_aladin_books', file=str(file), username='importer', dry_run=True, stdout=StringIO())
            self.assertEqual(Book.objects.count(), 0)
