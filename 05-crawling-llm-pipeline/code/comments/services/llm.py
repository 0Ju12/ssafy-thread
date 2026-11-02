"""
llm.py : LLM(GMS) 호출과 응답 해석 모듈

06_pipeline/llm.py 를 가져와 다음을 보완했습니다.
  - .env 는 Django settings.py 에서 한 번만 읽음 (여기서는 os.getenv 로 꺼내 쓰기만 함)
  - 키가 없거나 호출이 실패하면 LLMError 를 발생 -> 파이프라인에서 받아 화면에 안내 (F611)
"""

import json
import os

from openai import OpenAI


class LLMError(Exception):
    """LLM 호출 실패 (키 없음, 네트워크 오류, 응답 없음 등)"""


def run_llm(prompt):
    """prompt 를 LLM 에 보내고 응답 텍스트를 돌려준다"""
    api_key = os.getenv('GMS_KEY')
    if not api_key:
        raise LLMError('GMS_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요.')

    # GMS 는 OpenAI 와 같은 요청 형식을 제공 -> 주소(base_url)만 GMS 로 지정
    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv('GMS_BASE_URL', 'https://gms.ssafy.io/gmsapi/api.openai.com/v1').rstrip('/'),
        timeout=180.0,  # 고성능 모델 처리 시간을 고려한 요청 제한(초)
        max_retries=2,
    )
    try:
        # Responses API : 입력(input)을 보내고, 응답 객체를 돌려받음
        response = client.responses.create(
            model=os.getenv('MODEL', 'gpt-6.1-sol'),
            input=prompt,
        )
    except Exception as e:  # 인증 실패, 시간 초과, 네트워크 오류 등
        raise LLMError(f'LLM 호출 실패: {e}') from e

    # Responses API 의 최종 output_text 를 사용 (추론 과정은 포함하지 않음)
    # SDK/게이트웨이 버전에 따라 output_text 편의 속성이 없을 때도 대응
    text = (getattr(response, 'output_text', None) or '').strip()
    if not text:
        parts = []
        for item in (getattr(response, 'output', None) or []):
            for content in (getattr(item, 'content', None) or []):
                if getattr(content, 'type', '') == 'output_text':
                    value = getattr(content, 'text', '')
                    if value:
                        parts.append(value)
        text = '\n'.join(parts).strip()
    if not text:
        raise LLMError('LLM 응답이 비어 있습니다.')
    return text


def parse_json_array(response):
    """LLM 응답에서 JSON 배열을 꺼낸다. 형식이 틀리면 None"""
    text = response.strip()

    # 지시해도 응답을 ```json ... ``` 코드블럭으로 감싸 오는 경우가 있어 벗겨냄
    if text.startswith('```'):
        text = text.strip('`').removeprefix('json').strip()

    try:
        data = json.loads(text)  # '[0, 2, 5]' -> [0, 2, 5]
    except json.JSONDecodeError:
        # 앞뒤에 설명 문장이 붙은 경우 : 첫 '[' ~ 마지막 ']' 만 잘라 한 번 더 시도
        start, end = text.find('['), text.rfind(']')
        if start == -1 or end <= start:
            print('[파싱 실패] 응답이 JSON 형식이 아닙니다:', response[:100])
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            print('[파싱 실패] 응답이 JSON 형식이 아닙니다:', response[:100])
            return None

    if not isinstance(data, list):
        print('[파싱 실패] 응답이 리스트가 아닙니다:', response[:100])
        return None
    return data


def one_line(text):
    """프롬프트에 번호를 붙여 넣을 때 줄바꿈 때문에 번호가 어긋나지 않도록 한 줄로 만든다"""
    return ' '.join(str(text).split())
