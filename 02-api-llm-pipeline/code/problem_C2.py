import os
import requests
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# 1. [ 환경 변수 로드 ]
load_dotenv()

MY_TTBKEY = os.getenv('ALADIN_TTBKEY')
GMS_KEY = os.getenv('GMS_KEY')

ALADIN_SEARCH_URL = 'http://www.aladin.co.kr/ttb/api/ItemSearch.aspx'


# 2. OpenAI API 클라이언트 초기화
client = OpenAI(
    api_key=GMS_KEY,
    base_url="https://gms.ssafy.io/gmsapi/api.openai.com/v1"
)


# 3. [ 최대 100개까지 주제별 도서 데이터를 가져오는 함수 정의 ]
def fetch_books_by_topic(topic, max_results=100):
    page_size = 50
    all_items = []
    seen_ids = set()
    start = 1

    while len(all_items) < max_results:

        params = {
            'TTBKey': MY_TTBKEY,
            'Query': topic,
            'QueryType': 'Keyword',
            'MaxResults': page_size,
            'Start': start,
            'SearchTarget': 'Book',
            'output': 'js',
            'Version': '20131101',
        }

        response = requests.get(
            ALADIN_SEARCH_URL,
            params=params
        )

        response.raise_for_status()

        data = response.json()

        # 알라딘 API 에러 확인
        if 'errorCode' in data:
            print("알라딘 API 오류:")
            print(data)
            break

        items = data.get('item', [])

        # 검색 결과가 없으면 종료
        if not items:
            break

        for item in items:

            # isbn13 또는 itemId를 이용하여 중복 제거
            unique_id = (
                item.get('isbn13')
                or item.get('itemId')
            )

            if unique_id in seen_ids:
                continue

            seen_ids.add(unique_id)

            all_items.append(item)

            if len(all_items) >= max_results:
                break

        # 다음 페이지로 이동
        start += 1

    return all_items[:max_results]


# 4. 책 데이터를 ChatGPT로 분류하는 함수 정의 (습관, 시간관리, 독서법, 기타)
def classify_books_with_gpt(books):
    # 4.1 [ 분류할 책 제목들을 전달하기 편한 문자열로 취합 ]
    titles_text = "\n".join(
        f"{i}. {book.get('title', '')}"
        for i, book in enumerate(books, start=1)
    )

    # 4.2 [ ChatGPT 대화 메시지 설정 (프롬프트 작성) ]
    # 습관, 시간관리, 독서법, 기타 로 분류
    conversation_history = [
        {
            "role": "developer",
            "content": (
                "당신은 도서 제목을 보고 책의 주제를 분류하는 전문 사서입니다. "
                "각 책을 반드시 '습관', '시간관리', '독서법', '기타' 중 "
                "정확히 하나로 분류하세요. "
                "다른 설명은 하지 말고 반드시 JSON 객체 형식으로만 응답하세요."
            )
        },
        {
            "role": "user",
            "content": (
                "다음은 번호가 매겨진 도서 제목 목록입니다.\n\n"
                f"{titles_text}\n\n"
                "각 번호에 해당하는 책을 "
                "'습관', '시간관리', '독서법', '기타' 중 하나로 분류해주세요.\n\n"
                "반드시 다음과 같은 JSON 객체 형태로만 응답하세요.\n"
                '{"1": "습관", "2": "시간관리", "3": "독서법", "4": "기타"}'
            )
        }
    ]

    # 4.3 [ 생성형 AI에 분류 요청 보내기 ]
    # client.chat.completions.create() 호출 (example 코드 참고)
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=conversation_history
    )

    # 4.4 [ ChatGPT의 응답을 가져와 JSON 으로 추출 ]
    # ! 주의. JSON 형태로 프롬프팅을 하지 못하면 파싱에서 에러가 발생할 수 있습니다.
    content = response.choices[0].message.content

    content = content.strip()

    # 혹시 ```json 형태로 응답한 경우 제거
    if content.startswith("```json"):
        content = content[7:]

    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    category_by_index = json.loads(content)  # 응답에서 JSON 데이터를 추출하고 파싱

    classification = {
        '습관': [],
        '시간관리': [],
        '독서법': [],
        '기타': []
    }

    for i, book in enumerate(books, start=1):

        category = category_by_index.get(
            str(i),
            '기타'
        )

        # 혹시 GPT가 다른 카테고리를 반환하면 기타로 처리
        if category not in classification:
            category = '기타'

        classification[category].append(
            book.get('title', '')
        )

    return classification   # 분류 정보 반환


# 5. [ 데이터를 JSON 파일로 저장하는 함수 정의 ]
def save_to_json(data, filename):
    path = Path(filename)

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        'w',
        encoding='utf-8'
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# 6. '독서' 도서 데이터를 처리하는 함수 정의
def process_reading_books():
    # 6.1 [ '독서'와 관련된 도서 검색 (100개) ]
    books = fetch_books_by_topic('독서', 100)  # fetch_books_by_topic() 호출

    print(f"검색된 도서 수: {len(books)}권")

    # 검색 결과가 없으면 종료
    if not books:
        print("알라딘 API에서 검색된 도서가 없습니다.")
        return

    # 6.2 [ 생성형 AI를 이용해 책 분류 ]
    classification = classify_books_with_gpt(books)  # classify_books_with_gpt() 호출

    # 6.3 [ 분류된 책 정보를 JSON 파일로 저장 ]
    # output/reading_habits.json 으로 저장하기
    json_path = (
        Path(__file__).resolve().parent
        / 'output'
        / 'reading_habits.json'
    )

    save_to_json(classification, json_path)  # save_to_json() 호출

    # 완료 메시지 출력
    print("'output/reading_habits.json' 파일이 생성되었습니다.")


# 함수 실행
if __name__ == '__main__':
    process_reading_books()