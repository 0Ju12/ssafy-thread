"""
preprocess.py : 댓글 전처리 모듈 (F605)

06_pipeline/preprocess.py 를 가져와 다음을 보완했습니다.
  - 길이 필터를 명세 기준(5 이상 ~ 76 이하)에 맞춤. IQR 계산값도 함께 반환 (F602 저장 항목)
  - 불필요한 패턴(URL, ㅋㅋㅋ·ㅠㅠ 같은 자음·모음 반복) 제거 단계 추가
  - '3%' 의 % 와 '1.5' 의 소수점은 의미가 있어 남김
  - 중복 댓글 제거 추가
  - 단계별 변화(바뀐 댓글, 제거된 댓글)를 기록해 화면에 보여 줄 수 있게 반환
  - 부적절 댓글 프롬프트에서 줄바꿈 때문에 번호가 어긋나지 않도록 한 줄로 변환

    from comments.services.preprocess import CRITERIA, filter_inappropriate, clean_comments
    kept, removed = filter_inappropriate(comments, CRITERIA['basic'])
    cleaned, iqr_info, steps = clean_comments(kept)
"""

import math
import re

import pandas as pd

from .llm import LLMError, one_line, parse_json_array, run_llm

# ------------------------------------------------------------
# 부적절 댓글 제거 (LLM 판단 + 코드 제거)
# ------------------------------------------------------------
CRITERIA = {
    # 명세 프롬프트 예시와 같은 기준
    'basic': '욕설, 혐오, 비방, 선정성, 과도한 비난',
    'strict': (
        '욕설, 혐오, 비방, 선정성, 과도한 비난, 조롱·비꼬기, '
        '다른 투자자를 깎아내리는 표현, 근거 없는 단정이나 매수·매도를 부추기는 선동'
    ),
}


def build_filter_prompt(comments, criteria):
    """댓글에 번호를 붙이고, 기준에 해당하는 댓글의 "번호만" 돌려 달라는 프롬프트를 만든다"""
    numbered = '\n'.join(f'{i}. {one_line(c)}' for i, c in enumerate(comments))
    return f"""다음 댓글 목록에서 부적절한 댓글({criteria})의 번호(0 부터 시작)만 JSON 배열로 알려줘.
응답은 반드시 [0, 2, 5] 또는 [] 형식의 배열만 보내고, 설명이나 코드블럭은 쓰지 마.

댓글 목록:
{numbered}"""


def filter_inappropriate(comments, criteria, return_indices=False):
    """LLM 이 고른 번호의 댓글을 제거하고 (남은 댓글, 제거된 댓글)을 돌려준다

    LLM 호출 자체가 실패하면 LLMError 가 그대로 올라감 -> 파이프라인에서 처리
    """
    if not comments:
        return ([], [], []) if return_indices else ([], [])

    response = run_llm(build_filter_prompt(comments, criteria))
    print('  [LLM 응답]', response)

    numbers = parse_json_array(response)
    if numbers is None:
        # 형식 오류를 성공으로 취급하지 않는다. 파이프라인은 원본을 보존하고 경고를 남긴다.
        raise LLMError('부적절 댓글 판정 응답이 유효한 JSON 배열이 아닙니다.')

    # 정수이면서 실제 댓글 번호 범위 안인 값만 사용 (중복 제거 후 정렬)
    to_remove = sorted({n for n in numbers if type(n) is int and 0 <= n < len(comments)})

    # 앞에서부터 지우면 뒤쪽 번호가 밀리므로 뒤에서부터 제거
    kept = list(comments)
    kept_indices = list(range(len(comments)))
    removed = []
    for i in reversed(to_remove):
        removed.append(kept.pop(i))
        kept_indices.pop(i)
    removed.reverse()
    return (kept, removed, kept_indices) if return_indices else (kept, removed)


# ------------------------------------------------------------
# 정제 (pandas + 정규표현식)
# ------------------------------------------------------------
def _changed(df, before_col, after_col):
    changed = df[df[before_col] != df[after_col]]
    return [[b, a] for b, a in zip(changed[before_col], changed[after_col])]


def to_dataframe(comments, steps):
    """댓글 리스트를 DataFrame 으로 바꾸고, 결측치(None, 빈 문자열)를 제거한다"""
    df = pd.DataFrame({'comment': pd.Series(comments, dtype=object)})
    before = len(df)
    removed = [c for c in comments if c is None or not str(c).strip()]

    df = df.dropna(subset=['comment'])
    df['comment'] = df['comment'].astype(str).str.strip()
    df = df[df['comment'] != '']

    steps.append({'name': '결측치 제거', 'before': before, 'after': len(df),
                  'removed': [repr(r) for r in removed], 'changed': []})
    return df


# 불필요한 패턴 : (설명, 정규식, 바꿀 글자)
# re.compile : 정규표현식을 미리 "컴파일"해 두고 여러 번 재사용
NOISE_PATTERNS = [
    ('URL', re.compile(r'https?://\S+|www\.\S+'), ' '),
    ('자음·모음 반복(ㅋㅋ, ㅠㅠ 등)', re.compile(r'[ㄱ-ㅎㅏ-ㅣ]+'), ' '),
    ('반복 문장부호(!!!, ...)', re.compile(r'([!?.~^])\1+'), ' '),
]
# [^...] : 괄호 안의 문자가 "아닌" 것 -> 한글·영문·숫자·공백·%·마침표가 아닌 문자 (이모지·기호 등)
SPECIAL_CHARS = re.compile(r'[^가-힣a-zA-Z0-9\s%.+\-]')
# 주가의 음수·양수 부호는 의미가 있으므로 숫자 앞의 +/-는 보존한다.
UNRELATED_SIGNS = re.compile(r'[+\-](?!\d)')
# 숫자 사이(1.5)가 아닌 마침표
LONELY_DOT = re.compile(r'(?<!\d)\.|\.(?!\d)')
MULTI_SPACE = re.compile(r'\s+')


def remove_noise_patterns(df, steps):
    """URL, ㅋㅋㅋ 같은 불필요한 패턴을 지운다"""
    df['clean'] = df['comment']
    for _, pattern, repl in NOISE_PATTERNS:
        df['clean'] = df['clean'].apply(lambda x, p=pattern, r=repl: p.sub(r, x))
    df['clean'] = df['clean'].apply(lambda x: MULTI_SPACE.sub(' ', x).strip())

    steps.append({'name': '불필요한 패턴 제거', 'before': len(df), 'after': len(df),
                  'removed': [], 'changed': _changed(df, 'comment', 'clean'),
                  'detail': ', '.join(name for name, _, _ in NOISE_PATTERNS)})
    return df


def remove_special_chars(df, steps):
    """한글·영문·숫자·공백(+ %, 소수점)만 남기고 연속 공백을 한 칸으로 정리한다"""
    before_col = df['clean'].copy()
    df['clean'] = df['clean'].apply(lambda x: SPECIAL_CHARS.sub('', x))  # re.sub 와 같은 동작
    df['clean'] = df['clean'].apply(lambda x: UNRELATED_SIGNS.sub('', x))
    df['clean'] = df['clean'].apply(lambda x: LONELY_DOT.sub('', x))
    df['clean'] = df['clean'].apply(lambda x: MULTI_SPACE.sub(' ', x).strip())

    df['_before'] = before_col
    steps.append({'name': '특수문자·공백 정리', 'before': len(df), 'after': len(df),
                  'removed': [], 'changed': _changed(df, '_before', 'clean')})
    return df.drop(columns=['_before'])


def remove_meaningless(df, steps):
    """정리 후 비었거나, 숫자만 / 영어만 / 'none' 인 댓글을 제거한다"""
    cond_empty = df['clean'] == ''
    cond_numeric = df['clean'].str.match(r'^[\d\s%.]+$')
    cond_english = df['clean'].str.match(r'^[A-Za-z\s]+$')
    cond_none = df['clean'].str.lower() == 'none'
    cond_any = cond_empty | cond_numeric | cond_english | cond_none

    steps.append({'name': '의미 없는 댓글 제거', 'before': len(df), 'after': int((~cond_any).sum()),
                  'removed': df[cond_any]['comment'].tolist(), 'changed': []})
    return df[~cond_any]


def remove_duplicates(df, steps):
    """정리 후 같은 내용이 된 댓글은 하나만 남긴다"""
    dup = df.duplicated(subset=['clean'])
    steps.append({'name': '중복 제거', 'before': len(df), 'after': int((~dup).sum()),
                  'removed': df[dup]['clean'].tolist(), 'changed': []})
    return df[~dup]


def remove_length_outliers(df, steps, min_len=5, max_len=76, mode='clamp'):
    """길이 기준으로 너무 짧거나 긴 댓글을 제거하고 (DataFrame, IQR 정보)를 돌려준다

    mode
      clamp : IQR 정상 범위(Q1-1.5IQR ~ Q3+1.5IQR)를 min_len~max_len 안으로 제한
      fixed : min_len~max_len 고정 (IQR 은 계산해서 기록만)
    """
    df = df.copy()
    df['length'] = df['clean'].str.len()

    info = {'mode': mode, 'min_len': min_len, 'max_len': max_len,
            'q1': None, 'q3': None, 'iqr': None, 'iqr_lower': None, 'iqr_upper': None}

    if len(df) >= 4:  # 사분위수는 데이터가 너무 적으면 의미가 없음
        q1 = float(df['length'].quantile(0.25))
        q3 = float(df['length'].quantile(0.75))
        iqr = q3 - q1
        info.update(q1=q1, q3=q3, iqr=iqr,
                    iqr_lower=round(q1 - 1.5 * iqr, 2), iqr_upper=round(q3 + 1.5 * iqr, 2))

    if mode == 'clamp' and info['iqr'] is not None:
        lower = max(min_len, info['iqr_lower'])
        upper = min(max_len, info['iqr_upper'])
        if lower > upper:  # 분포가 특이해 범위가 뒤집히면 고정 기준 사용
            lower, upper = min_len, max_len
    else:
        lower, upper = min_len, max_len
    # 글자 수는 정수 -> 실제로 적용되는 범위를 정수로 (예: 40.25 -> 40자 이하)
    lower, upper = math.ceil(lower), math.floor(upper)
    info['lower'], info['upper'] = lower, upper

    cond_outlier = (df['length'] < lower) | (df['length'] > upper)
    steps.append({'name': '길이 이상치 제거', 'before': len(df), 'after': int((~cond_outlier).sum()),
                  'removed': [f"{t} ({n}자)" for t, n in zip(df[cond_outlier]['clean'], df[cond_outlier]['length'])],
                  'changed': [], 'detail': f'정상 범위 {lower:g} ~ {upper:g}자'})
    print(f"[길이 이상치] Q1={info['q1']}, Q3={info['q3']}, IQR={info['iqr']} -> {lower:g} ~ {upper:g}자")
    return df[~cond_outlier], info


def clean_comments(comments, min_len=5, max_len=76, mode='clamp', with_sources=False):
    """정제 단계를 차례로 적용하고 (정제된 댓글 리스트, IQR 정보, 단계별 기록)을 돌려준다"""
    steps = []
    df = to_dataframe(comments, steps)
    if df.empty:
        base = ([], {'mode': mode, 'min_len': min_len, 'max_len': max_len,
                    'lower': min_len, 'upper': max_len}, steps)
        return (*base, []) if with_sources else base
    df = remove_noise_patterns(df, steps)
    df = remove_special_chars(df, steps)
    df = remove_meaningless(df, steps)
    df = remove_duplicates(df, steps)
    df, iqr_info = remove_length_outliers(df, steps, min_len, max_len, mode)
    base = (df['clean'].tolist(), iqr_info, steps)
    return (*base, df.index.tolist()) if with_sources else base
