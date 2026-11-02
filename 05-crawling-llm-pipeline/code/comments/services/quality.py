"""증강 결과의 숫자·방향 무결성 검사와 변경 부분의 안전한 HTML 표시.

규칙 기반 검사는 완벽한 의미 검증이 아닙니다. 방향성이 모호한 문장은 '확인 필요'가
될 수 있으며, '통과'는 AI가 내용을 정확히 보존했다는 보증이 아닙니다.
"""
from difflib import SequenceMatcher
from html import escape
import re

NUMBER_TOKEN = re.compile(r"(?<!\d)[+\-]?\d+(?:\.\d+)?%?")
# 같은 댓글의 긍정적인 사실(상승)과 부정적인 사실(하락)을 동시에 말할 수도 있다.
# 따라서 '반대 방향만 나타나는 경우'에만 명백한 의미 뒤집힘으로 취급한다.
UP_WORDS = re.compile(r'상승|급등|폭등|반등|오르|올랐|올라|올릴|상한가|증가|매수|빨간불')
DOWN_WORDS = re.compile(r'하락|급락|폭락|떨어|내려|내렸|내리|하한가|감소|매도|파란불|손절')


def assess_pair(source, augmented, stock_name=""):
    """원문/증강 문장 검증: ok/review 와 사유 목록을 반환."""
    issues = []
    if not isinstance(augmented, str) or not augmented.strip():
        return {'status': 'review', 'issues': ['증강 문장이 비어 있거나 텍스트가 아닙니다.']}
    orig_nums = NUMBER_TOKEN.findall(source)
    out_nums = NUMBER_TOKEN.findall(augmented)
    if orig_nums != out_nums:
        issues.append('숫자·백분율·부호가 원문과 다릅니다.')
    source_up, source_down = bool(UP_WORDS.search(source)), bool(DOWN_WORDS.search(source))
    out_up, out_down = bool(UP_WORDS.search(augmented)), bool(DOWN_WORDS.search(augmented))
    if source_up and not source_down and out_down and not out_up:
        issues.append('상승 표현이 하락 표현으로 바뀐 것으로 보입니다.')
    elif source_down and not source_up and out_up and not out_down:
        issues.append('하락 표현이 상승 표현으로 바뀐 것으로 보입니다.')
    if stock_name and stock_name in source and stock_name not in augmented:
        issues.append('원문에 있는 종목명이 증강 문장에서 사라졌습니다.')
    if source.strip() == augmented.strip():
        issues.append('증강 후에도 표현이 동일합니다.')
    return {'status': 'review' if issues else 'ok', 'issues': issues}


def review_pairs(cleaned, augmented, stock_name=""):
    return [dict(index=i, original=source, augmented=out, **assess_pair(source, out, stock_name=stock_name))
            for i, (source, out) in enumerate(zip(cleaned, augmented))]


def highlight_difference(source, target):
    """HTML 이스케이프를 거친 후 변경된 구간만 mark 태그로 감싼다."""
    if not isinstance(source, str) or not isinstance(target, str):
        return escape(str(target))
    pieces = []
    for op, _a, _b, c, d in SequenceMatcher(None, source, target, autojunk=False).get_opcodes():
        if op == 'delete':
            continue
        content = escape(target[c:d])
        pieces.append(f'<mark class="diff-highlight">{content}</mark>' if op != 'equal' else content)
    return ''.join(pieces)
