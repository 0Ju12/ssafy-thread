"""
pipeline.py : 회사명 하나로 전체 파이프라인 실행 (F603 ~ F607, F610, F611)

06_pipeline/run_pipeline.py 의 run_pipeline() 을 가져와 다음을 보완했습니다.
  - 원본 / 부적절 제거 / 정제 / 증강을 모두 결과에 담고, 단계(stage)로 구분한 통합 결과(records) 생성 (F607)
  - 실제종목명, IQR 임계값, 정제 단계 기록 포함 (F602 저장 항목)
  - 댓글 요약 (F610)
  - 상태(status)·안내 메시지(message)·경고(warnings) : 실패 원인을 화면에 안내 (F611)
  - progress 콜백 : 진행 상황을 터미널과 웹 화면에 전달 (F603 선택)

    from comments.services.pipeline import run_pipeline
    result = run_pipeline('삼성')
"""

from datetime import datetime

from django.conf import settings

from . import crawler
from .augment import augment_comments
from .llm import LLMError
from .preprocess import CRITERIA, clean_comments, filter_inappropriate
from .summary import summarize_comments
from .quality import review_pairs


def _print_progress(stage, message):
    print(f'[{stage}] {message}')


def build_records(raw, removed, cleaned, augmented, kept_raw_indices=None, clean_origins=None):
    """원본·제거·정제·증강 데이터를 하나의 결과 집합으로 통합한다 (단계 구분 가능)"""
    removed_left = list(removed)
    kept_raw_indices = kept_raw_indices if kept_raw_indices is not None else list(range(len(raw)))
    clean_origins = clean_origins if clean_origins is not None else list(range(len(cleaned)))
    removed_index_set = set(range(len(raw))) - set(kept_raw_indices)
    records = []
    for i, text in enumerate(raw):
        # 원본 댓글이 부적절 판정으로 제거되었는지 표시 (같은 내용이 여러 개여도 한 번씩만)
        is_removed = i in removed_index_set if kept_raw_indices is not None else text in removed_left
        if is_removed and text in removed_left:
            removed_left.remove(text)
        records.append({'stage': 'original', 'index': i, 'text': text, 'removed': is_removed})
    for i, text in enumerate(removed):
        records.append({'stage': 'removed', 'index': i, 'text': text})
    for i, text in enumerate(cleaned):
        records.append({'stage': 'clean', 'index': i, 'text': text,
                        'source_index': kept_raw_indices[clean_origins[i]] if i < len(clean_origins) and clean_origins[i] < len(kept_raw_indices) else None})
    for i, text in enumerate(augmented):
        # origin_index : 몇 번째 정제 댓글에서 만들어졌는지
        records.append({'stage': 'augmented', 'index': i, 'text': text, 'origin_index': i,
                        'source_index': kept_raw_indices[clean_origins[i]] if i < len(clean_origins) and clean_origins[i] < len(kept_raw_indices) else None})
    return records


def run_pipeline(company, limit=None, criteria_name=None, headless=None,
                 use_sample=None, with_summary=True, progress=None):
    """수집 => 부적절 제거 => 정제 => 증강 => 요약을 차례로 실행하고 결과 딕셔너리를 돌려준다"""
    limit = limit or settings.COMMENT_LIMIT
    criteria_name = criteria_name or settings.FILTER_CRITERIA
    if criteria_name not in CRITERIA:
        criteria_name = 'basic'
    headless = settings.CRAWLER_HEADLESS if headless is None else headless
    use_sample = settings.USE_SAMPLE_DATA if use_sample is None else use_sample
    progress = progress or _print_progress

    result = {
        'query': company,
        'status': crawler.STATUS_OK,
        'message': '',
        'warnings': [],
        'stock_name': '',
        'stock_code': '',
        'collected_at': datetime.now().isoformat(timespec='seconds'),
        'criteria_name': criteria_name,
        'criteria': CRITERIA[criteria_name],
        'raw': [], 'removed': [], 'clean': [], 'augmented': [],
        'iqr_info': {}, 'clean_steps': [], 'summary': '', 'records': [],
        'quality_checks': [], 'market_snapshot': {},
        'counts': {'collected': 0, 'filtered': 0, 'cleaned': 0, 'augmented': 0},
    }

    # ---------------- 1. 수집 (F603, F604) ----------------
    progress('crawl', f"'{company}' 크롤링을 시작합니다")
    log = lambda msg: progress('crawl', msg)  # noqa: E731
    if use_sample:
        fetched = crawler.fetch_sample_comments(company, settings.SAMPLE_DATA_PATH, limit, log)
    else:
        fetched = crawler.fetch_comments(company, limit=limit, headless=headless, log=log)

    result.update(stock_name=fetched['stock_name'], stock_code=fetched['stock_code'],
                  market_snapshot=fetched.get('market_snapshot') or {})
    if result['market_snapshot'].get('warnings') and not use_sample:
        result['warnings'].append('일부 시장정보를 수집하지 못했습니다. 결과의 시장 현황에서 확인하세요.')
    if fetched['status'] != crawler.STATUS_OK:
        # 회사 없음 / 댓글 없음 / 브라우저 오류 -> 뒤 단계를 건너뛰고 안내 (F611)
        result.update(status=fetched['status'], message=fetched['message'])
        print(f"[안내] {fetched['message']}")  # 화면 안내는 뷰에서 한 번만 표시
        return result

    raw = fetched['comments']
    result['raw'] = raw
    result['counts']['collected'] = len(raw)
    progress('crawl', f"{result['stock_name']} 댓글 {len(raw)}개 수집 완료")

    # ---------------- 2. 부적절 댓글 제거 (F605, LLM) ----------------
    progress('filter', f'LLM 으로 부적절한 댓글을 판별합니다 ({criteria_name} 기준)')
    try:
        kept, removed, kept_indices = filter_inappropriate(raw, CRITERIA[criteria_name], return_indices=True)
    except LLMError as e:
        kept, removed, kept_indices = list(raw), [], list(range(len(raw)))
        result['warnings'].append(f'부적절 댓글 판별을 건너뛰었습니다: {e}')
    result['removed'] = removed
    result['counts']['filtered'] = len(kept)
    progress('filter', f'부적절 댓글 {len(removed)}개 제거')

    # ---------------- 3. 정제 (F605) ----------------
    progress('clean', '특수문자·불필요한 패턴·길이 기준으로 정제합니다')
    cleaned, iqr_info, steps, clean_origins = clean_comments(
        kept, settings.LENGTH_MIN, settings.LENGTH_MAX, settings.LENGTH_FILTER_MODE, with_sources=True
    )
    result.update(clean=cleaned, iqr_info=iqr_info, clean_steps=steps)
    result['counts']['cleaned'] = len(cleaned)
    progress('clean', f"정제 완료 : {len(kept)}개 -> {len(cleaned)}개 "
                      f"(길이 {iqr_info['lower']:g} ~ {iqr_info['upper']:g}자)")

    if not cleaned:
        result['warnings'].append('전처리 후 남은 댓글이 없어 증강을 건너뛰었습니다.')

    # ---------------- 4. 증강 (F606) ----------------
    if cleaned:
        progress('augment', 'LLM 으로 의미를 유지한 증강 문장을 생성합니다')
        try:
            augmented = augment_comments(cleaned, stock_name=result['stock_name'])
            if not augmented:
                result['warnings'].append('증강 결과의 형식·개수가 맞지 않아 사용하지 않았습니다.')
        except LLMError as e:
            augmented = []
            result['warnings'].append(f'증강을 건너뛰었습니다: {e}')
        result['augmented'] = augmented
        result['quality_checks'] = review_pairs(cleaned, augmented, stock_name=result['stock_name'])
        if any(q['status'] == 'review' for q in result['quality_checks']):
            result['warnings'].append('일부 증강 문장은 품질 검토가 필요합니다. 문장 비교 탭에서 확인하세요.')
        result['counts']['augmented'] = len(augmented)
        progress('augment', f'증강 문장 {len(augmented)}개 생성')

    # ---------------- 5. 요약 (F610) ----------------
    if with_summary:
        progress('summary', '전체 댓글을 요약합니다')
        try:
            result['summary'] = summarize_comments(result['stock_name'], raw)
            progress('summary', '요약 완료')
        except LLMError as e:
            result['warnings'].append(f'요약을 생성하지 못했습니다: {e}')

    # ---------------- 6. 통합 (F607) ----------------
    result['records'] = build_records(raw, result['removed'], result['clean'], result['augmented'],
                                      kept_indices, clean_origins)
    return result
