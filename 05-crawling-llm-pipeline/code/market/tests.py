"""토스증권 라이브 요청 없이 Selenium 파싱·수집 캐시·화면 렌더링 테스트."""
from unittest.mock import patch
from django.test import TestCase
from django.core.cache import cache
from .models import MarketCapture
from .scraper import parse_overview, parse_rank_text
from .services import capture_with_driver, fetch_market, fetch_fx, market_ranks
from .demo import demo_market, demo_fx

class SeleniumMarketTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_missing_snapshot_is_not_fake(self):
        self.assertEqual(fetch_market()['indices'], [])
        self.assertEqual(fetch_fx()['rates'], [])
        self.assertTrue(fetch_market(demo=True)['demo'])
        self.assertEqual(len(fetch_market(demo=True)['indices']),2)

    @patch('market.services.scrape_snapshot')
    def test_capture_with_existing_driver_saved_once(self, scrape):
        snapshot={'captured_at':'2026-10-30T14:00:00+09:00','warnings':[],
                  'market':{'indices':[{'name':'KOSPI','value':2500,'change_pct':1}],
                            'stocks':[],'ranking_lists':{},'error':'','as_of':'2026-10-30'},
                  'fx':{'rates':[{'symbol':'USD/KRW','value':1400}], 'history':[]}}
        scrape.return_value=snapshot
        fake_driver=object()
        capture_with_driver(fake_driver)
        scrape.assert_called_once()
        self.assertEqual(scrape.call_args.args[0],fake_driver)
        self.assertEqual(MarketCapture.objects.count(),1)
        self.assertEqual(fetch_market()['indices'][0]['value'],2500)
        self.assertEqual(fetch_fx()['rates'][0]['value'],1400)

    def test_demo_dashboard(self):
        response=self.client.get('/market/?demo=1')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'DEMO MODE')
        self.assertContains(response,'KOSPI')
        self.assertContains(response,'KOSDAQ')

    def test_empty_market_does_not_show_example_values(self):
        response=self.client.get('/market/?demo=0')
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'2674.32')

    def test_refresh_requires_post(self):
        self.assertEqual(self.client.get('/market/refresh/').status_code,405)

    def test_snapshot_partial_ranks(self):
        sample={'ranking_lists':{'rise':[{'name':'A','market':'미분류','change_pct':10,'code':''}]},
                'stocks':[]}
        self.assertEqual(len(market_ranks(sample)['rise']['ALL']),1)
        self.assertEqual(len(market_ranks(sample)['rise']['KOSPI']),0)
