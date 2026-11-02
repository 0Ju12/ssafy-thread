"""
augment.py : 텍스트 데이터 증강 모듈 (F606)

06_pipeline/augment.py 를 가져와 다음을 보완했습니다.
  - 형식·개수 검증에 실패하면 한 번 더 요청 (재시도)
  - 프롬프트에 "숫자·상승/하락 방향은 바꾸지 말 것" 조건 추가 (의미 유지)
"""

import re

from .llm import one_line, parse_json_array, run_llm
from .quality import assess_pair

NUMBER_TOKEN = re.compile(r"(?<!\d)[+\-]?\d+(?:\.\d+)?%?")


def build_augment_prompt(comments):
    """각 문장을 의미는 유지하고 표현만 바꿔 달라는 프롬프트를 만든다"""
    numbered = '\n'.join(f'{i}. {one_line(c)}' for i, c in enumerate(comments))
    return f"""다음 {len(comments)}개 주식 커뮤니티 댓글을 각각 의미는 유지하면서 다른 표현으로 바꿔줘.
- 입력과 같은 순서, 같은 개수({len(comments)}개)로
- 가격·퍼센트 같은 숫자와 오른다/내린다 같은 방향, 감정(긍정·부정)은 바꾸지 마
- ["문장1", "문장2"] 형식의 JSON 배열만 보내고, 번호·설명·코드블럭은 쓰지 마

문장 목록:
{numbered}"""


def augment_comments(comments, max_attempts=2, stock_name=""):
    """LLM 으로 문장을 증강하고, 형식·개수가 맞을 때만 결과를 돌려준다

    max_attempts 번 모두 실패하면 [] (LLM 호출 자체의 실패는 LLMError 로 올라감)
    """
    if not comments:
        return []

    for attempt in range(1, max_attempts + 1):
        print(f'[증강] LLM 호출 중... (입력 {len(comments)}개, {attempt}회차)')
        augmented = parse_json_array(run_llm(build_augment_prompt(comments)))

        if augmented is None:
            continue
        if len(augmented) != len(comments):
            print(f'[검증 실패] 입력 {len(comments)}개, 응답 {len(augmented)}개')
            continue
        # 배열 개수만 맞아도 null, 숫자, 빈 문자열이 섞이면 데이터가 훼손될 수 있다.
        if any(not isinstance(a, str) or not a.strip() for a in augmented):
            print('[검증 실패] 증강 결과에 문자열이 아닌 항목 또는 빈 문장이 있습니다')
            continue
        # 금융 댓글에서 숫자·부호가 달라지면 의미가 바뀌므로 보수적으로 재시도한다.
        failed = [assess_pair(src, out, stock_name=stock_name) for src, out in zip(comments, augmented)]
        if any(item['status'] == 'review' and
               any('숫자' in issue or '상승' in issue or '하락' in issue or '종목명' in issue for issue in item['issues'])
               for item in failed):
            print('[검증 실패] 숫자·부호·상승/하락 방향이 바뀐 증강 문장을 발견했습니다')
            continue
        return [a.strip() for a in augmented]

    return []
