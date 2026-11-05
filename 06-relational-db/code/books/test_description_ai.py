import json
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model
from books.models import Book
from books.description_ai import needs_description, generate_description, AI_PREFIX


class DescriptionGenerationTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='description_tester', password='safe-password-123')
        self.missing = Book.objects.create(user=user, title='빛과 밤', author='테스트 저자', rating=3,
                                           description='도서 소개는 출처 데이터셋에 포함되지 않았습니다.')
        self.original = Book.objects.create(user=user, title='원본 도서', author='다른 저자', rating=3,
                                            description='출판사가 제공한 소개입니다.')

    def test_placeholder_detection(self):
        self.assertTrue(needs_description('제공된 도서 데이터에 소개가 없습니다.'))
        self.assertFalse(needs_description('도서의 주제를 소개합니다.'))
        self.assertFalse(needs_description(AI_PREFIX + '\n이미 생성됨'))

    def test_dry_run_does_not_modify(self):
        with patch('books.management.commands.generate_book_descriptions.generate_description') as mock_ai:
            call_command('generate_book_descriptions', '--dry-run')
            mock_ai.assert_not_called()
        self.missing.refresh_from_db()
        self.assertTrue(needs_description(self.missing.description))

    def test_command_updates_only_missing_and_is_repeat_safe(self):
        text = AI_PREFIX + '\n책 제목이 떠올리게 하는 질문을 중심으로 독서의 실마리를 제안합니다.'
        with patch('books.management.commands.generate_book_descriptions.generate_description', return_value=text) as mock_ai:
            call_command('generate_book_descriptions', '--delay', '0')
            call_command('generate_book_descriptions', '--delay', '0')
            self.assertEqual(mock_ai.call_count, 1)
        self.missing.refresh_from_db(); self.original.refresh_from_db()
        self.assertEqual(self.missing.description, text)
        self.assertEqual(self.original.description, '출판사가 제공한 소개입니다.')

    def test_failed_call_preserves_data(self):
        with patch('books.management.commands.generate_book_descriptions.generate_description', side_effect=ValueError('API 실패')):
            call_command('generate_book_descriptions', '--delay', '0')
        self.missing.refresh_from_db()
        self.assertTrue(needs_description(self.missing.description))

    def test_api_response_and_disclosure(self):
        response = SimpleNamespace(__enter__=None)
        class APIResponse:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return json.dumps({'output':[{'content':[{'type':'output_text','text':'제목을 통해 빛과 밤이라는 두 이미지의 대비를 생각해 볼 수 있습니다. 책을 읽으며 어떤 질문을 발견하게 될지 기대해 보세요.'}]}]}).encode()
        with patch('books.description_ai.urllib.request.urlopen', return_value=APIResponse()) as urlopen:
            text = generate_description(self.missing, api_key='dummy', base_url='https://gms.example/v1')
        self.assertTrue(text.startswith(AI_PREFIX))
        self.assertIn('빛과 밤', text)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'https://gms.example/v1/responses')
