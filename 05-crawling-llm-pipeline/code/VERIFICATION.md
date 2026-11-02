# ThRead Selenium 시장 동시 수집 — 확인 결과

## 코드 적용 상태

| 검사 | 결과 | 방법 |
|---|---|---|
| KRX / 토스 Open API 키 없이 시장정보 수집 경로 | 통과 (코드 정적 확인) | `market/services.py` -> `market/scraper.py` -> 기존 ChromeDriver |
| 댓글과 같은 브라우저 재사용 | 통과 (코드 정적 확인) | `comments/services/crawler.py`에서 메인 시장 수집 후 동일 `driver`로 종목 검색 |
| 환율·지수 부호 보존 | 통과 | `scripts/test_market_parser.py` |
| 상승/하락 분리, 거래대금 억 단위 변환 | 통과 | `scripts/test_market_parser.py` |
| 시장 데이터 없는 경우 가짜 데이터 미생성 | 통과 | 파서 단위테스트 및 코드 검사 |
| 댓글 결과에 같은 시점 시장 스냅샷 저장 | 연결 확인 | `CrawlResult.market_snapshot`, 마이그레이션 0003 |
| 시점별 시장 그래프 | 연결 확인 | `MarketCapture`, 마이그레이션 0001, `captured_history()` |
| 기존 11개 디자인 출력 위치 | 통과 (템플릿 연결 정적 확인) | 4종 상세 레이아웃 + 부모 11개 CSS |
| Python 문법, JS 문법, ZIP 무결성 | 통과 | `compileall`, `node --check`, `ZipFile.testzip()` |
| Django 테스트/실제 사이트 Selenium end-to-end | **미실행** | 작업 환경에 Django/Selenium 패키지·토스증권 사이트 네트워크 접근 없음 |

## 실사이트에서 반드시 확인할 것

1. `http://127.0.0.1:8000/market/`에서 **Selenium 새로 수집** (정상 수집이면 지수·달러 환율·랭킹 표시).
2. `http://127.0.0.1:8000/`에서 `삼성` 분석 후 결과 페이지 **댓글 수집 당시 시장 정보** 카드 확인.
3. 두 시점에 수집한 뒤 그래프가 2개 이상의 **실제 기록**으로만 만들어졌는지 확인.
4. 크롬 사이트 구조에 따라 순위 버튼을 찾지 못하면 `market/scraper.py`의 `_switch_rank()`와 `parse_rank_text()`를 개발자 도구로 수정.
5. `python manage.py check`, `python manage.py migrate`, `python manage.py test comments market` 성공 확인.

## 한계/정확성

- 사이트 텍스트 스냅샷과 실제 사이트 UI는 언제든 달라질 수 있습니다. 공개 사이트의 과거 텍스트 형태에 대한 파서 검증이지 최신 DOM에 대한 E2E 성공 주장이 아닙니다.
- 시장지수·달러 환율은 **홈 화면 표시값**으로, 시세 확정 기준일/실시간 체결가/은행 고시 환율을 보증하지 않습니다.
- 랭킹은 **공개 화면 현재 표시 순위에 한정**합니다. 종목코드·시장 구분·거래량은 확인된 경우만 제공합니다. 데이터가 없을 때 0으로 표시하거나 임의 값을 넣지 않습니다.
- 금융 데이터 사용은 제공자의 자동 수집 정책과 표시·재사용 허용 범위를 검토한 후 사용하세요.
