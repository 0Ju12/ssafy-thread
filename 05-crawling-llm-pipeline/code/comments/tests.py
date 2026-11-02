"""
자동 테스트 : python manage.py test

토스증권·GMS 에 실제로 접속하지 않도록 크롤러는 샘플 데이터, LLM 은 가짜 함수로 바꿔서 검사한다.
"""

import json
from io import StringIO
from unittest import mock

from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from .models import CrawlResult
from .services import crawler, pipeline
from .services.llm import LLMError, parse_json_array, run_llm
from .services.augment import augment_comments
from .services.preprocess import clean_comments, filter_inappropriate


def fake_llm(prompt):
    """프롬프트 종류에 따라 그럴듯한 응답을 돌려주는 가짜 LLM"""
    import re
    lines = re.findall(r'^(\d+)\. (.*)$', prompt, re.M)
    if '부적절한 댓글' in prompt:
        return json.dumps([int(i) for i, t in lines if '작살' in t or '리딩방' in t])
    if '다른 표현으로' in prompt:
        return '```json\n' + json.dumps([t + ' (증강)' for _, t in lines], ensure_ascii=False) + '\n```'
    return '전반적 분위기: 혼재\n주요 내용:\n- 테스트 요약'


class ParseJsonArrayTests(TestCase):
    def test_variants(self):
        self.assertEqual(parse_json_array('[0, 2]'), [0, 2])
        self.assertEqual(parse_json_array('```json\n[1]\n```'), [1])
        self.assertEqual(parse_json_array('결과는 [3, 4] 입니다'), [3, 4])
        self.assertIsNone(parse_json_array('없음'))
        self.assertIsNone(parse_json_array('{"a": 1}'))


class PreprocessTests(TestCase):
    def test_length_range_and_patterns(self):
        comments = [
            '오늘 22만만 지켜라!!', '1127', 'ㅋㅋㅋ', '던져', None, '   ',
            '23만 뚫자~ ㅋㅋㅋ', 'https://spam.example.com 무료 리딩방', '3%에서 동결입니다.',
            '가' * 80, 'lol ok', '오늘 22만만 지켜라',
        ]
        cleaned, info, steps = clean_comments(comments)
        # 모든 결과가 명세 기준 5 이상 ~ 76 이하
        self.assertTrue(all(5 <= len(c) <= 76 for c in cleaned))
        self.assertTrue(all(info['lower'] <= len(c) <= info['upper'] for c in cleaned))
        # 패턴·특수문자 제거
        self.assertFalse(any('ㅋ' in c or 'http' in c or '!' in c for c in cleaned))
        self.assertIn('3%에서 동결입니다', cleaned)  # % 는 의미가 있어 남김
        self.assertIn('23만 뚫자', cleaned)
        # 중복('오늘 22만만 지켜라')은 하나만
        self.assertEqual(cleaned.count('오늘 22만만 지켜라'), 1)
        # IQR 정보 기록 (F602)
        for key in ('q1', 'q3', 'iqr', 'lower', 'upper', 'min_len', 'max_len'):
            self.assertIn(key, info)
        self.assertEqual([s['name'] for s in steps][0], '결측치 제거')

    @override_settings()
    def test_fixed_mode(self):
        comments = ['가나다라마' + '바' * i for i in range(0, 72, 3)]
        cleaned, info, _ = clean_comments(comments, mode='fixed')
        self.assertEqual((info['lower'], info['upper']), (5, 76))
        self.assertTrue(all(5 <= len(c) <= 76 for c in cleaned))

    def test_empty(self):
        cleaned, info, steps = clean_comments([])
        self.assertEqual(cleaned, [])

    def test_filter_removes_from_back(self):
        comments = ['A', 'B', 'C', 'D']
        with mock.patch('comments.services.preprocess.run_llm', return_value='[2, 1, 1, 9, "x"]'):
            kept, removed = filter_inappropriate(comments, '기준')
        self.assertEqual(kept, ['A', 'D'])
        self.assertEqual(removed, ['B', 'C'])

    def test_filter_unparsable_emits_error_for_warning(self):
        with mock.patch('comments.services.preprocess.run_llm', return_value='모르겠어요'):
            with self.assertRaises(LLMError):
                filter_inappropriate(['A', 'B'], '기준')

    def test_numeric_sign_survives_preprocessing(self):
        comments = ['오늘 -3% 떨어졌어요', '오늘 +3% 상승했어요']
        cleaned, _, _ = clean_comments(comments, mode='fixed')
        self.assertIn('오늘 -3% 떨어졌어요', cleaned)
        self.assertIn('오늘 +3% 상승했어요', cleaned)

    def test_decimal_and_sign_preserved(self):
        cleaned, _, _ = clean_comments(['주가가 -5.4% 하락했습니다'], mode='fixed')
        self.assertEqual(cleaned, ['주가가 -5.4% 하락했습니다'])


class AugmentIntegrityTests(TestCase):
    def test_non_string_or_empty_response_is_rejected(self):
        with mock.patch('comments.services.augment.run_llm', side_effect=['[null]', '[""]']):
            self.assertEqual(augment_comments(['원본 문장입니다']), [])

    def test_numeric_direction_is_not_silently_changed(self):
        with mock.patch('comments.services.augment.run_llm', side_effect=[
            '["오늘 +3% 올랐어요"]', '["오늘 -3% 하락했어요 (동일 내용)"]'
        ]):
            self.assertEqual(augment_comments(['오늘 -3% 하락했어요']),
                             ['오늘 -3% 하락했어요 (동일 내용)'])


class CrawlerHelperTests(TestCase):
    def test_driver_service_fallback(self):
        # 설정으로 끄거나, webdriver-manager 가 실패하면 None -> Selenium Manager 로 전환
        with mock.patch.dict('os.environ', {'USE_WEBDRIVER_MANAGER': '0'}):
            self.assertIsNone(crawler.get_driver_service())
        with mock.patch.dict('os.environ', {'USE_WEBDRIVER_MANAGER': '1'}), \
                mock.patch('webdriver_manager.chrome.ChromeDriverManager.install', side_effect=OSError('차단')), \
                mock.patch('sys.stdout', new=StringIO()):
            self.assertIsNone(crawler.get_driver_service())

    def test_clean_title(self):
        self.assertEqual(crawler.clean_title('삼성전자 - 토스증권'), '삼성전자')
        self.assertEqual(crawler.clean_title('삼성전자 주가 | 토스증권'), '삼성전자')
        self.assertEqual(crawler.clean_title('토스증권'), '')


@override_settings(USE_SAMPLE_DATA=True)
@mock.patch('comments.services.summary.run_llm', side_effect=fake_llm)
@mock.patch('comments.services.augment.run_llm', side_effect=fake_llm)
@mock.patch('comments.services.preprocess.run_llm', side_effect=fake_llm)
class PipelineTests(TestCase):
    def test_full_pipeline(self, *_):
        r = pipeline.run_pipeline('삼성', progress=lambda s, m: None)
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(r['stock_name'], '삼성전자')
        self.assertEqual(r['counts']['collected'], 20)
        self.assertEqual(r['removed'], ['http://example.com 무료 리딩방 입장하세요'])
        self.assertEqual(len(r['augmented']), len(r['clean']))
        stages = {rec['stage'] for rec in r['records']}
        self.assertEqual(stages, {'original', 'removed', 'clean', 'augmented'})
        self.assertTrue(r['summary'])
        self.assertEqual(r['warnings'], [])

    def test_llm_failure_is_reported(self, m_pre, m_aug, m_sum):
        m_pre.side_effect = LLMError('키 없음')
        m_aug.side_effect = LLMError('키 없음')
        m_sum.side_effect = LLMError('키 없음')
        r = pipeline.run_pipeline('삼성', progress=lambda s, m: None)
        self.assertEqual(r['status'], 'ok')  # 수집·정제 결과는 살림
        self.assertEqual(len(r['warnings']), 3)
        self.assertEqual(r['augmented'], [])

    def test_augment_retry_on_count_mismatch(self, m_pre, m_aug, m_sum):
        answers = iter(['["하나"]', None])

        def flaky(prompt):
            a = next(answers)
            return a if a is not None else fake_llm(prompt)
        m_aug.side_effect = flaky
        r = pipeline.run_pipeline('삼성', progress=lambda s, m: None)
        self.assertEqual(len(r['augmented']), len(r['clean']))


@override_settings(USE_SAMPLE_DATA=True)
@mock.patch('comments.services.summary.run_llm', side_effect=fake_llm)
@mock.patch('comments.services.augment.run_llm', side_effect=fake_llm)
@mock.patch('comments.services.preprocess.run_llm', side_effect=fake_llm)
class ViewTests(TransactionTestCase):
    def test_index(self, *_):
        res = self.client.get(reverse('comments:index'))
        self.assertContains(res, '댓글 증강 시스템')

    def test_every_theme_renders(self, *_):
        # .env 의 UI_THEME 로 고를 수 있는 11가지 디자인이 모두 오류 없이 그려지는지
        with mock.patch('sys.stdout', new=StringIO()):
            self.client.post(reverse('comments:run'), {'company': '삼성'})
        pk = CrawlResult.objects.get().pk
        for theme in ('clean', 'board', 'proof', 'chat', 'desk', 'story', 'aurora', 'atelier', 'brutal', 'glass', 'console'):
            with self.settings(UI_THEME=theme):
                index = self.client.get(reverse('comments:index'))
                detail = self.client.get(reverse('comments:detail', args=[pk]))
            self.assertContains(index, f'theme-{theme}.css')
            self.assertContains(detail, f'theme-{theme}.css')
            if theme in ('glass', 'console'):
                self.assertContains(detail, 'theme-desk.css')
            elif theme == 'brutal':
                self.assertContains(detail, 'theme-story.css')
            for text in ('삼성전자', '원본 데이터', '증강', '댓글 요약', '통합 데이터', 'IQR', 'company-form', 'progress-panel', 'fail-box'):
                self.assertContains(detail, text)

    @override_settings(SHOW_THEME_SWITCHER=False)
    def test_default_theme(self, *_):
        res = self.client.get(reverse('comments:index') + '?theme=board')
        self.assertContains(res, 'theme-clean.css')  # 전환 링크가 꺼져 있으면 기본 테마 고정
        self.assertNotContains(res, '디자인 후보')

    @override_settings(SHOW_THEME_SWITCHER=True)
    def test_theme_switch(self, *_):
        for theme in ('clean', 'board', 'proof'):
            res = self.client.get(reverse('comments:index') + f'?theme={theme}')
            self.assertContains(res, f'theme-{theme}.css')
        res = self.client.get(reverse('comments:index') + '?theme=nope')
        self.assertContains(res, 'theme-proof.css')  # 잘못된 값이면 기존 테마 유지

    def test_empty_input_does_nothing(self, *_):
        with mock.patch('comments.views.run_pipeline') as m, mock.patch('sys.stdout', new=StringIO()) as out:
            res = self.client.post(reverse('comments:run'), {'company': '   '})
            res2 = self.client.post(reverse('comments:run_stream'), {'company': ''})
        m.assert_not_called()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res2.status_code, 204)
        self.assertNotIn('[입력]', out.getvalue())
        self.assertEqual(CrawlResult.objects.count(), 0)

    def test_run_prints_saves_and_redirects(self, *_):
        with mock.patch('sys.stdout', new=StringIO()) as out:
            res = self.client.post(reverse('comments:run'), {'company': '삼성'})
        self.assertIn('[입력] 회사명 : 삼성', out.getvalue())  # F601 터미널 출력
        obj = CrawlResult.objects.get()
        self.assertRedirects(res, reverse('comments:detail', args=[obj.pk]))
        self.assertEqual(obj.stock_name, '삼성전자')
        self.assertEqual(len(obj.raw_comments), 20)
        self.assertTrue(obj.iqr_info)

        page = self.client.get(reverse('comments:detail', args=[obj.pk]))
        for text in ('원본 데이터', '20개', '전처리 후', '증강 데이터', '통합 데이터', '댓글 요약', 'IQR'):
            self.assertContains(page, text)

    def test_stream(self, *_):
        with mock.patch('sys.stdout', new=StringIO()):
            res = self.client.post(reverse('comments:run_stream'), {'company': '삼성'})
            lines = [json.loads(x) for x in b''.join(res.streaming_content).decode().splitlines()]
        self.assertEqual(lines[0]['stage'], 'input')
        self.assertEqual(lines[-1]['type'], 'done')
        self.assertTrue(any(x.get('stage') == 'augment' for x in lines))

    def test_no_company_message(self, *_):
        fail = crawler.make_result('no_company', 'ㅁㄴㅇㄹ', "'ㅁㄴㅇㄹ' 에 해당하는 회사를 찾지 못했습니다.")
        with mock.patch('comments.services.crawler.fetch_sample_comments', return_value=fail), \
                mock.patch('sys.stdout', new=StringIO()):
            res = self.client.post(reverse('comments:run'), {'company': 'ㅁㄴㅇㄹ'})
            stream = self.client.post(reverse('comments:run_stream'), {'company': 'ㅁㄴㅇㄹ'})
            last = json.loads(b''.join(stream.streaming_content).decode().splitlines()[-1])
        self.assertContains(res, '회사를 찾지 못했습니다')
        self.assertEqual(last['type'], 'fail')
        self.assertEqual(CrawlResult.objects.filter(status='no_company').count(), 2)

    def test_regenerate_summary(self, m_pre, m_aug, m_sum):
        with mock.patch('sys.stdout', new=StringIO()):
            self.client.post(reverse('comments:run'), {'company': '삼성'})
        obj = CrawlResult.objects.get()
        m_sum.side_effect = lambda p: '새 요약'
        res = self.client.post(reverse('comments:summary', args=[obj.pk]))
        obj.refresh_from_db()
        self.assertEqual(obj.summary, '새 요약')
        self.assertEqual(res.status_code, 302)


class GMSModelTests(TestCase):
    @mock.patch.dict('os.environ', {'GMS_KEY': 'test-key', 'MODEL': 'gpt-6.1-sol', 'GMS_BASE_URL': 'https://gms.ssafy.io/gmsapi/api.openai.com/v1'})
    @mock.patch('comments.services.llm.OpenAI')
    def test_responses_api_uses_gms_model(self, openai_cls):
        # 실제 요청은 하지 않고 Responses API 호출 인자만 검사
        openai_cls.return_value.responses.create.return_value.output_text = '응답 완료'
        result = run_llm('안녕하세요')
        self.assertEqual(result, '응답 완료')
        openai_cls.assert_called_once()
        self.assertEqual(openai_cls.call_args.kwargs['api_key'], 'test-key')
        self.assertEqual(openai_cls.call_args.kwargs['base_url'], 'https://gms.ssafy.io/gmsapi/api.openai.com/v1')
        openai_cls.return_value.responses.create.assert_called_once_with(model='gpt-6.1-sol', input='안녕하세요')

    @mock.patch.dict('os.environ', {'GMS_KEY': 'test-key', 'MODEL': 'gpt-6.1-sol'})
    @mock.patch('comments.services.llm.OpenAI')
    def test_output_content_fallback(self, openai_cls):
        from types import SimpleNamespace
        response = SimpleNamespace(
            output_text=None,
            output=[SimpleNamespace(content=[SimpleNamespace(type='output_text', text='문장 증강 성공')])],
        )
        openai_cls.return_value.responses.create.return_value = response
        self.assertEqual(run_llm('증강해줘'), '문장 증강 성공')


class QualityAndInsightTests(TestCase):
    def test_direction_flip_rejected(self):
        from .services.quality import assess_pair
        self.assertEqual(assess_pair('주가가 -3% 급락했습니다', '주가가 -3% 급등했습니다')['status'], 'review')
        self.assertEqual(assess_pair('오늘 +3% 상승했습니다', '오늘 +3% 올랐습니다')['status'], 'ok')
        self.assertEqual(assess_pair('삼성전자 주가 하락', '주가 하락', stock_name='삼성전자')['status'], 'review')

    def test_diff_escapes_user_supplied_html(self):
        from .services.quality import highlight_difference
        html = highlight_difference('안녕하세요', '<script>alert(1)</script>')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_cleaned_origin_indices_survive_duplicates_and_removals(self):
        from .services.preprocess import clean_comments
        raw = ['오늘의 거래량이 많네요', '오늘의 거래량이 많네요', '주가는 -3% 하락했습니다']
        clean, info, steps, origins = clean_comments(raw, mode='fixed', with_sources=True)
        self.assertEqual(origins, [0, 2])
        from .services.pipeline import build_records
        records = build_records(raw, [], clean, [t + ' 변경' for t in clean], [0, 1, 2], origins)
        self.assertEqual([r['source_index'] for r in records if r['stage'] == 'clean'], [0, 2])

    def test_keywords_and_distribution_use_real_comments(self):
        from .services.insights import make_insights
        class Result:
            raw_comments = ['오늘 삼성전자 상승', '삼성전자 거래량 증가']
            clean_comments = ['삼성전자 상승', '삼성전자 거래량 증가']
            removed_comments = []
            augmented_comments = ['삼성전자 올랐음']
        x = make_insights(Result())
        self.assertEqual(sum(y['count'] for y in x['lengths']), 2)
        self.assertEqual(x['keywords'][0]['word'], '삼성전자')

    def test_crawler_keeps_two_same_text_in_one_viewport(self):
        from unittest.mock import Mock
        driver = Mock()
        driver.find_elements.return_value = [Mock(text='동일 댓글입니다'), Mock(text='동일 댓글입니다')]
        driver.execute_script.return_value = None
        seen, comments = set(), []
        crawler.read_visible_comments(driver, comments, seen)
        crawler.read_visible_comments(driver, comments, seen)
        self.assertEqual(comments, ['동일 댓글입니다', '동일 댓글입니다'])


@override_settings(USE_SAMPLE_DATA=True)
@mock.patch('comments.services.summary.run_llm', side_effect=fake_llm)
@mock.patch('comments.services.augment.run_llm', side_effect=fake_llm)
@mock.patch('comments.services.preprocess.run_llm', side_effect=fake_llm)
class EnhancedViewTests(TestCase):
    def setUp(self):
        self.current = CrawlResult.objects.create(
            query='삼성', stock_name='삼성전자', stock_code='A005930', status='ok',
            raw_comments=['새로 생긴 댓글', '=1+1'], clean_comments=['새로 생긴 댓글'],
            augmented_comments=['새롭게 생긴 댓글'],
            records=[{'stage': 'original', 'index': 0, 'text': '새로 생긴 댓글'},
                     {'stage': 'original', 'index': 1, 'text': '=1+1'},
                     {'stage': 'clean', 'index': 0, 'text': '새로 생긴 댓글', 'source_index': 0},
                     {'stage': 'augmented', 'index': 0, 'text': '새롭게 생긴 댓글',
                      'origin_index': 0, 'source_index': 0}],
            iqr_info={'min_len': 5, 'max_len': 76, 'lower': 5, 'upper': 76},
        )

    def test_csv_export_filter_and_injection_protection(self, *_):
        url = reverse('comments:export', args=[self.current.pk, 'csv'])
        res = self.client.get(url + '?stage=original')
        self.assertEqual(res.status_code, 200)
        self.assertIn('attachment;', res['Content-Disposition'])
        decoded = res.content.decode('utf-8-sig')
        self.assertIn("'=1+1", decoded)
        self.assertNotIn('새롭게 생긴 댓글', decoded)

    def test_json_export_filter(self, *_):
        url = reverse('comments:export', args=[self.current.pk, 'json'])
        data = json.loads(self.client.get(url + '?stage=augmented').content)
        self.assertEqual(data['stock_name'], '삼성전자')
        self.assertEqual(len(data['records']), 1)
        self.assertEqual(data['records'][0]['stage'], 'augmented')
        self.assertEqual(self.client.get(url + '?stage=bad').status_code, 404)

    def test_history_same_stock_only(self, *_):
        previous = CrawlResult.objects.create(
            query='삼성전자', stock_name='삼성전자', stock_code='A005930', status='ok',
            raw_comments=['과거 댓글'], clean_comments=['과거 댓글'],
        )
        other = CrawlResult.objects.create(
            query='카카오', stock_name='카카오', stock_code='A035720', status='ok')
        url = reverse('comments:compare_history', args=[self.current.pk])
        response = self.client.get(url + f'?other={previous.pk}')
        self.assertContains(response, '과거 댓글')
        self.assertContains(response, '새로 생긴 댓글')
        self.assertEqual(self.client.get(url + f'?other={other.pk}').status_code, 404)

    def test_all_themes_include_enhancements(self, *_):
        for theme in ('clean', 'board', 'proof', 'chat', 'desk', 'story',
                      'aurora', 'atelier', 'brutal', 'glass', 'console'):
            with self.settings(UI_THEME=theme, SHOW_THEME_SWITCHER=False):
                res = self.client.get(reverse('comments:detail', args=[self.current.pk]))
            self.assertContains(res, 'CSV 다운로드')
            self.assertContains(res, '실제 댓글 데이터 인사이트')
            self.assertContains(res, 'AI 증강 문장 검증')
            self.assertContains(res, '댓글')
