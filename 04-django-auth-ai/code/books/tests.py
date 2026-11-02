from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from . import ai
from .models import Book

User = get_user_model()
PASSWORD = 'ssafy-pass-1234!'
VALID = {
    'title': '데미안',
    'description': '1919년에 간행된 헤르만 헤세의 소설.',
    'customer_review_rank': 9,
    'author': '헤르만 헤세',
}
FAKE_PROFILE = {
    'author_info': '헤르만 헤세는 독일계 스위스인 소설가이다.',
    'author_works': 'Demian, Steppenwolf',
    'author_image': 'https://upload.wikimedia.org/hesse.jpg',
}


@mock.patch('books.views.generate_author_profile', return_value=FAKE_PROFILE)
class BookViewTests(TestCase):
    def setUp(self):
        User.objects.create_user(username='tester', password=PASSWORD)
        self.book = Book.objects.create(**VALID)

    def login(self):
        self.client.login(username='tester', password=PASSWORD)

    # F412 index ------------------------------------------------------------
    def test_index_lists_books_with_detail_link(self, _):
        res = self.client.get(reverse('books:index'))
        self.assertContains(res, '데미안')
        self.assertContains(res, reverse('books:detail', args=[self.book.pk]))
        self.assertEqual(self.client.post(reverse('books:index')).status_code, 405)

    def test_root_redirects_home(self, _):
        self.assertRedirects(self.client.get('/'), reverse('books:index'))

    # F413 create -----------------------------------------------------------
    def test_create_requires_login(self, _):
        res = self.client.get(reverse('books:create'))
        self.assertRedirects(res, reverse('accounts:login') + '?next=' + reverse('books:create'))

    def test_create_valid_saves_and_redirects_detail(self, gen):
        self.login()
        res = self.client.post(reverse('books:create'), {**VALID, 'title': '노인과 바다'})
        book = Book.objects.get(title='노인과 바다')
        self.assertRedirects(res, reverse('books:detail', args=[book.pk]))
        gen.assert_called_once()
        self.assertEqual(book.author_works, 'Demian, Steppenwolf')  # F417 저장

    def test_create_invalid_not_saved(self, gen):
        self.login()
        res = self.client.post(reverse('books:create'), {**VALID, 'title': '', 'customer_review_rank': 11})
        self.assertEqual(res.status_code, 200)
        self.assertIn('title', res.context['form'].errors)
        self.assertIn('customer_review_rank', res.context['form'].errors)
        self.assertEqual(Book.objects.count(), 1)
        gen.assert_not_called()

    # F414 detail -----------------------------------------------------------
    def test_detail_shows_fields_and_buttons(self, _):
        self.book.author_info = FAKE_PROFILE['author_info']
        self.book.author_works = FAKE_PROFILE['author_works']
        self.book.save()
        res = self.client.get(reverse('books:detail', args=[self.book.pk]))
        for text in ('데미안', '헤르만 헤세', '9 / 10', 'BACK', 'Demian, Steppenwolf',
                     '작가 대표작과 작가 정보는 AI가 생성한 정보로, 정확하지 않을 수 있습니다.'):
            self.assertContains(res, text)
        self.assertNotContains(res, 'UPDATE')  # 로그아웃 상태
        self.login()
        res = self.client.get(reverse('books:detail', args=[self.book.pk]))
        self.assertContains(res, 'UPDATE')
        self.assertContains(res, 'DELETE')
        self.assertEqual(self.client.get(reverse('books:detail', args=[999])).status_code, 404)

    # F415 update -----------------------------------------------------------
    def test_update_prefilled_and_saves(self, gen):
        self.login()
        res = self.client.get(reverse('books:update', args=[self.book.pk]))
        self.assertEqual(res.context['form'].initial['title'], '데미안')
        res = self.client.post(reverse('books:update', args=[self.book.pk]), {**VALID, 'title': '데미안(개정판)'})
        self.assertRedirects(res, reverse('books:detail', args=[self.book.pk]))
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, '데미안(개정판)')
        gen.assert_not_called()  # 저자가 같으면 다시 생성하지 않음
        self.client.post(reverse('books:update', args=[self.book.pk]), {**VALID, 'author': '어니스트 헤밍웨이'})
        gen.assert_called_once()

    def test_update_requires_login(self, _):
        res = self.client.post(reverse('books:update', args=[self.book.pk]), VALID)
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse('accounts:login'), res.url)

    # F416 delete -----------------------------------------------------------
    def test_delete_post_only_login_only(self, _):
        url = reverse('books:delete', args=[self.book.pk])
        self.client.post(url)
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())  # 비로그인
        self.login()
        self.assertEqual(self.client.get(url).status_code, 405)
        res = self.client.post(url)
        self.assertRedirects(res, reverse('books:index'))
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())


class AuthorAIFailureTests(TestCase):
    """F417 : AI 실패해도 도서는 저장되고 경고만 표시"""

    def setUp(self):
        User.objects.create_user(username='tester', password=PASSWORD)
        self.client.login(username='tester', password=PASSWORD)

    @override_settings(GMS_KEY='')
    def test_no_key_still_saves_book(self):
        res = self.client.post(reverse('books:create'), VALID, follow=True)
        self.assertEqual(Book.objects.count(), 1)
        self.assertContains(res, 'GMS_KEY')
        self.assertContains(res, 'AI 작가 정보 생성하기')


def fake_client(output_text, status='completed'):
    """GMS Responses API 응답을 흉내 내는 가짜 클라이언트"""
    client = mock.Mock()
    client.responses.create.return_value = mock.Mock(status=status, output_text=output_text, usage=None)
    return client


class AIModuleTests(TestCase):
    def test_parse_llm_json_with_code_fence(self):
        text = '```json\n{"author_info": "소개", "author_works": ["A", "B"]}\n```'
        self.assertEqual(ai.parse_llm_json(text)['author_works'], ['A', 'B'])

    @override_settings(GMS_KEY='test-key', GMS_MODEL='gpt-5-nano')
    def test_generate_author_profile_flow(self):
        wiki = {'title': '헤르만 헤세', 'url': 'u', 'extract': '독일 작가', 'image': 'https://img/h.jpg'}
        client = fake_client('{"author_info": "헤세는 작가다.", "author_works": ["데미안", "싯다르타"]}')
        with mock.patch.object(ai, 'search_wikipedia', return_value=wiki), \
                mock.patch.object(ai, '_get_client', return_value=client):
            result = ai.generate_author_profile('헤르만 헤세', '데미안', '소설')
        self.assertEqual(result['author_works'], '데미안, 싯다르타')
        self.assertEqual(result['author_image'], 'https://img/h.jpg')
        # Responses API 로 요청했는지 확인
        kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(kwargs['model'], 'gpt-5-nano')
        self.assertEqual(kwargs['text'], {'format': {'type': 'json_object'}})
        self.assertEqual(kwargs['reasoning'], {'effort': 'low'})
        self.assertIn('독일 작가', kwargs['input'])

    @override_settings(GMS_KEY='test-key')
    def test_llm_error_raises_friendly_error(self):
        with mock.patch.object(ai, 'search_wikipedia', return_value=None), \
                mock.patch.object(ai, '_get_client', side_effect=RuntimeError('boom')):
            with self.assertRaises(ai.AuthorInfoError):
                ai.generate_author_profile('누군가')

    @override_settings(GMS_KEY='test-key')
    def test_incomplete_response_is_error(self):
        client = fake_client('{"author_', status='incomplete')
        with mock.patch.object(ai, 'search_wikipedia', return_value=None), \
                mock.patch.object(ai, '_get_client', return_value=client):
            with self.assertRaises(ai.AIError):
                ai.generate_author_profile('누군가')

    @override_settings(GMS_KEY='test-key', GMS_MODEL='gpt-6.1-sol')
    def test_ping_like_curl_with_custom_model(self):
        """curl 예시와 같은 요청 : {"model": GMS_MODEL, "input": "Hello, World!"}"""
        client = fake_client('Hello! How can I help you?')
        with mock.patch.object(ai, '_get_client', return_value=client):
            self.assertEqual(ai.ping(), 'Hello! How can I help you?')
        kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(kwargs, {'model': 'gpt-6.1-sol', 'input': 'Hello, World!'})

    @override_settings(GMS_KEY='')
    def test_no_key(self):
        with self.assertRaises(ai.AIError):
            ai.ping()


@override_settings(GMS_KEY='test-key')
class ExtraAIFeatureTests(TestCase):
    """추가 기능 : AI 도서 분석 · AI 맞춤 도서 추천"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='tester', password=PASSWORD, interested_genres='NOVEL', age=25)
        self.book = Book.objects.create(**VALID)
        self.other = Book.objects.create(**{**VALID, 'title': '노인과 바다', 'author': '어니스트 헤밍웨이'})

    def login(self):
        self.client.login(username='tester', password=PASSWORD)

    def test_analyze_saves_and_shows(self):
        client = fake_client(
            '{"summary": "성장 소설", "keywords": ["성장", "자아"], '
            '"target_readers": "청소년", "reading_points": ["싱클레어의 변화"]}')
        self.login()
        with mock.patch.object(ai, '_get_client', return_value=client):
            res = self.client.post(reverse('books:analyze', args=[self.book.pk]), follow=True)
        self.book.refresh_from_db()
        self.assertEqual(self.book.ai_analysis['keywords'], ['성장', '자아'])
        self.assertContains(res, '#성장')
        self.assertContains(res, '이런 분께 추천해요')

    def test_analyze_post_only_and_login_required(self):
        url = reverse('books:analyze', args=[self.book.pk])
        self.assertEqual(self.client.post(url).status_code, 302)  # 비로그인 → 로그인 화면
        self.login()
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_analyze_failure_shows_warning(self):
        self.login()
        with mock.patch.object(ai, '_get_client', side_effect=RuntimeError('boom')):
            res = self.client.post(reverse('books:analyze', args=[self.book.pk]), follow=True)
        self.assertContains(res, 'AI 도서 분석에 실패했습니다')
        self.book.refresh_from_db()
        self.assertEqual(self.book.ai_analysis, {})

    def test_recommend_only_existing_books(self):
        # AI 가 목록에 없는 id(9999)를 섞어 보내도 버리고, 있는 도서만 보여 줌
        client = fake_client(
            '{"recommendations": [{"id": %d, "reason": "고전 성장 소설"}, {"id": 9999, "reason": "가짜"}]}'
            % self.other.pk)
        self.login()
        with mock.patch.object(ai, '_get_client', return_value=client):
            res = self.client.post(reverse('accounts:recommend'), follow=True)
        self.assertContains(res, '노인과 바다')
        self.assertContains(res, '고전 성장 소설')
        self.assertNotContains(res, '가짜')
        prompt = client.responses.create.call_args.kwargs['input']
        self.assertIn('소설/시/희곡', prompt)  # 회원의 관심 장르가 프롬프트에 들어감
        # 세션에 저장되어 프로필을 다시 열어도 유지
        res = self.client.get(reverse('accounts:profile', args=['tester']))
        self.assertContains(res, '고전 성장 소설')

    def test_recommend_post_only(self):
        self.login()
        self.assertEqual(self.client.get(reverse('accounts:recommend')).status_code, 405)

    def test_analyze_empty_result_not_saved(self):
        # 형식이 맞지 않는 응답(예: 다른 기능의 JSON)이 오면 빈 분석을 저장하지 않음
        client = fake_client('{"recommendations": []}')
        self.login()
        with mock.patch.object(ai, '_get_client', return_value=client):
            res = self.client.post(reverse('books:analyze', args=[self.book.pk]), follow=True)
        self.assertContains(res, '결과가 비어 있습니다')
        self.book.refresh_from_db()
        self.assertEqual(self.book.ai_analysis, {})


def aladin_item(n, **extra):
    item = {
        'title': f'신간 {n} - 부제', 'author': f'작가{n} (지은이), 번역가 (옮긴이)',
        'description': f'신간 {n}의 소개 &lt;설명&gt;', 'customerReviewRank': n % 11, 'adult': False,
    }
    item.update(extra)
    return item


def aladin_response(items):
    response = mock.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {'item': items}
    return response


@override_settings(ALADIN_TTBKEY='ttb-test')
class AladinImportTests(TestCase):
    """알라딘 API 로 최신 도서 가져오기 (python manage.py import_books)"""

    def run_command(self, *args):
        from io import StringIO

        from django.core.management import call_command
        out = StringIO()
        call_command('import_books', *args, stdout=out)
        return out.getvalue()

    def test_import_100_books_over_pages(self):
        page1 = [aladin_item(n) for n in range(1, 51)]
        page2 = [aladin_item(n) for n in range(51, 101)] + [aladin_item(n) for n in range(101, 111)]
        with mock.patch('books.aladin.requests.get', side_effect=[aladin_response(page1), aladin_response(page2)]) as get:
            out = self.run_command()
        self.assertEqual(Book.objects.count(), 100)
        self.assertIn('새로 추가 100권', out)
        book = Book.objects.get(title='신간 3')  # 부제 제거
        self.assertEqual(book.author, '작가3')     # 대표 저자만
        self.assertEqual(book.description, '신간 3의 소개 <설명>')  # HTML 엔티티 변환
        params = get.call_args_list[0].kwargs['params']
        self.assertEqual(params['QueryType'], 'ItemNewSpecial')
        self.assertEqual(params['ttbkey'], 'ttb-test')
        self.assertEqual(params['output'], 'js')

    def test_skip_invalid_and_duplicates_and_rerun(self):
        items = [
            aladin_item(1), aladin_item(1),            # 중복
            aladin_item(2, description=''),            # 설명 없음
            aladin_item(3, adult=True),                # 성인 도서
            aladin_item(4, customerReviewRank=None),   # 평점 없음 → 0
        ]
        with mock.patch('books.aladin.requests.get', side_effect=[aladin_response(items), aladin_response([])]):
            self.run_command('--count', '10')
        self.assertEqual(sorted(Book.objects.values_list('title', flat=True)), ['신간 1', '신간 4'])
        self.assertEqual(Book.objects.get(title='신간 4').customer_review_rank, 0)
        # 다시 실행해도 중복 저장되지 않음
        with mock.patch('books.aladin.requests.get', side_effect=[aladin_response(items), aladin_response([])]):
            out = self.run_command('--count', '10')
        self.assertEqual(Book.objects.count(), 2)
        self.assertIn('갱신 2권', out)

    def test_dry_run_and_fixture(self):
        import json
        import tempfile
        from pathlib import Path
        items = [aladin_item(n) for n in range(1, 6)]
        with mock.patch('books.aladin.requests.get', return_value=aladin_response(items)):
            self.run_command('--count', '5', '--dry-run')
        self.assertEqual(Book.objects.count(), 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'aladin.json'
            with mock.patch('books.aladin.requests.get', return_value=aladin_response(items)):
                self.run_command('--count', '5', '--save-fixture', str(path))
            data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual([d['pk'] for d in data], [1001, 1002, 1003, 1004, 1005])

    def test_api_error_message(self):
        from django.core.management.base import CommandError
        error = mock.Mock()
        error.raise_for_status.return_value = None
        error.json.return_value = {'errorCode': 2, 'errorMessage': '잘못된 TTBKey 입니다.'}
        with mock.patch('books.aladin.requests.get', return_value=error):
            with self.assertRaisesMessage(CommandError, '잘못된 TTBKey'):
                self.run_command()

    def test_warn_when_fewer_than_requested(self):
        items = [aladin_item(n) for n in range(1, 4)]
        with mock.patch('books.aladin.requests.get', side_effect=[aladin_response(items), aladin_response([])]):
            out = self.run_command('--count', '300')
        self.assertIn('요청한 300권 중 3권만', out)
        self.assertEqual(Book.objects.count(), 3)    

    @override_settings(ALADIN_TTBKEY='')
    def test_no_key(self):
        from django.core.management.base import CommandError
        with self.assertRaisesMessage(CommandError, 'TTBKEY'):
            self.run_command()
