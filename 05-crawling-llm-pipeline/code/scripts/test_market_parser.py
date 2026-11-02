"""Django/Selenium 네트워크 없이 실제 화면 텍스트 형태를 사용한 파서 점검."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from market.scraper import parse_overview, parse_rank_text, to_number

PAGE = '''
토스증권 사칭 유의 안내
국내 정규장 09:00 ~ 15:30
지수 목록
코스피 기관 순매도 부담
5,955.66-56.78(0.94%)
개인+8,260
코스닥 외국인·기관 매도
755.16-16.12(2.09%)
달러 환율
1,336.60+0.3(0.02%)
주요 일정
오늘 FOMC 회의 결과
실시간 차트 지금 뜨는 산업
실시간 차트
필터
전체
국내
해외
급상승
급하락
순위·오늘 14:47 기준
현재가
등락률
거래대금 순
시가총액
토스증권 AI 요약
1
SK하이닉스
1,545,000원
+3.90%
314억원
1,100.9조원
60 40
2
삼성전자
232,500원
-3.92%
232억원
1,586.9조원
더 보기
'''

class MarketParserTests(unittest.TestCase):
    def test_index_and_fx_signs(self):
        idx, fx, warns=parse_overview(PAGE)
        self.assertEqual(len(idx),2)
        self.assertEqual(len(fx),1)
        self.assertEqual(idx[0]['value'],5955.66)
        self.assertEqual(idx[0]['change_pct'],-.94)
        self.assertEqual(idx[1]['change'],-16.12)
        self.assertEqual(fx[0]['value'],1336.6)
        self.assertEqual(fx[0]['change_pct'],.02)
        self.assertEqual(warns,[])

    def test_ranking_positive_negative(self):
        codes={'삼성전자':'005930','SK하이닉스':'000660'}
        gainers=parse_rank_text(PAGE,codes,kind='rise')
        losers=parse_rank_text(PAGE,codes,kind='fall')
        self.assertEqual([x['name'] for x in gainers],['SK하이닉스'])
        self.assertEqual([x['name'] for x in losers],['삼성전자'])
        self.assertEqual(gainers[0]['value'],31400000000)
        self.assertEqual(gainers[0]['code'],'000660')

    def test_no_fake_data_when_structure_changed(self):
        a,b,w=parse_overview('검색창만 있는 비어 있는 페이지')
        self.assertFalse(a)
        self.assertFalse(b)
        self.assertTrue(w)
        self.assertFalse(parse_rank_text('검색창만 있는 페이지'))

    def test_units(self):
        self.assertEqual(to_number('314억원'),31_400_000_000)
        self.assertEqual(to_number('1.5조원'),1_500_000_000_000)
        self.assertIsNone(to_number('없음'))

if __name__ == '__main__': unittest.main(verbosity=2)
