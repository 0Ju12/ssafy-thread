"""
summary.py : 댓글 요약 모듈 (F610, 심화)

수집된 "전체" 댓글(원본)을 LLM 에 보내 주요 내용을 요약한다.
"""

from .llm import one_line, run_llm


def build_summary_prompt(stock_name, comments):
    numbered = '\n'.join(f'- {one_line(c)}' for c in comments)
    return f"""다음은 토스증권 커뮤니티에 올라온 '{stock_name}' 종목 댓글 {len(comments)}개야.
투자자들의 주요 의견을 한국어로 요약해줘.

형식
전반적 분위기: (긍정 / 부정 / 혼재 중 하나와 한 줄 설명)
주요 내용:
- (핵심 의견 3~5개, 각각 한 줄)

욕설이나 비방 표현은 옮기지 말고, 투자 권유는 하지 마.

댓글 목록:
{numbered}"""


def summarize_comments(stock_name, comments):
    """댓글 목록을 요약한 문자열을 돌려준다 (LLM 실패 시 LLMError)"""
    if not comments:
        return ''
    return run_llm(build_summary_prompt(stock_name, comments)).strip()
