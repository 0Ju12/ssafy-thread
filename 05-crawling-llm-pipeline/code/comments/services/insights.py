"""실제 수집/저장 데이터로 만든 통계. 인위적 감성 점수나 시세를 생성하지 않는다."""
from collections import Counter
import re

STOPWORDS = {'오늘', '내일', '이거', '그냥', '그리고', '그런데', '것은', '있는', '없다',
             '하는', '합니다', '해서', '라고', '으로', '같은', '진짜', '너무', '다들',
             '종목', '댓글', '생각', '대한', '정말', '아니', '뭔가', '있음', '없음'}
WORD_RE = re.compile(r'[가-힣A-Za-z]{2,}')
LENGTH_RANGES = [(0, 10, '1~10자'), (11, 20, '11~20자'), (21, 40, '21~40자'),
                 (41, 76, '41~76자'), (77, float('inf'), '77자 이상')]


def top_keywords(comments, count=8):
    # 형태소 분석을 사용하지 않은 단순 띄어쓰기 기반 빈도. '감성 분석'으로 해석하지 않음.
    words = Counter()
    for comment in comments:
        for word in WORD_RE.findall(comment):
            if word not in STOPWORDS and len(word) >= 2:
                words[word] += 1
    return [{'word': word, 'count': n} for word, n in words.most_common(count)]


def make_insights(result):
    raw = result.raw_comments or []
    clean = result.clean_comments or []
    augmented = result.augmented_comments or []
    lengths = [len(t) for t in raw]
    distribution = []
    for low, high, title in LENGTH_RANGES:
        amount = sum(low <= x <= high for x in lengths)
        distribution.append({'label': title, 'count': amount,
                             'pct': round(amount / len(lengths) * 100, 1) if lengths else 0})
    stats = [
        {'label': '원본 수집', 'count': len(raw), 'pct': 100 if raw else 0},
        {'label': 'LLM 제거 후', 'count': max(0, len(raw) - len(result.removed_comments)),
         'pct': round((len(raw)-len(result.removed_comments)) / len(raw)*100, 1) if raw else 0},
        {'label': '전처리 완료', 'count': len(clean),
         'pct': round(len(clean)/len(raw)*100, 1) if raw else 0},
        {'label': 'AI 증강 생성', 'count': len(augmented),
         'pct': round(len(augmented)/len(raw)*100, 1) if raw else 0},
    ]
    return {'lengths': distribution, 'steps': stats,
            'keywords': top_keywords(clean or raw),
            'avg_length': round(sum(lengths)/len(lengths), 1) if lengths else 0,
            'keyword_note': '띄어쓰기 기반 단어 빈도이며 감성 점수가 아닙니다.'}


def compare_result_data(current, previous):
    cur = Counter(current.raw_comments or [])
    old = Counter(previous.raw_comments or [])
    fresh = list((cur - old).elements())
    lost = list((old - cur).elements())
    cur_keywords = {item['word']: item['count'] for item in top_keywords(current.clean_comments or current.raw_comments)}
    old_keywords = {item['word']: item['count'] for item in top_keywords(previous.clean_comments or previous.raw_comments)}
    keys = list(dict.fromkeys(list(cur_keywords)+list(old_keywords)))[:12]
    return {
        'counts': [
            {'name': '원본', 'before': len(previous.raw_comments), 'after': len(current.raw_comments), 'delta': len(current.raw_comments)-len(previous.raw_comments)},
            {'name': '정제', 'before': len(previous.clean_comments), 'after': len(current.clean_comments), 'delta': len(current.clean_comments)-len(previous.clean_comments)},
            {'name': '증강', 'before': len(previous.augmented_comments), 'after': len(current.augmented_comments), 'delta': len(current.augmented_comments)-len(previous.augmented_comments)},
        ],
        'fresh': fresh[:30], 'lost': lost[:30], 'fresh_count': len(fresh), 'lost_count': len(lost),
        'keywords': [{'word': k, 'before': old_keywords.get(k, 0), 'after': cur_keywords.get(k, 0)} for k in keys],
    }
