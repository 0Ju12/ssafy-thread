import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# 1. [ 환경 변수 로드 ]
load_dotenv()
MY_TTBKEY = os.getenv('ALADIN_TTBKEY')
ALADIN_SEARCH_URL = 'http://www.aladin.co.kr/ttb/api/ItemSearch.aspx'


# 2. [ 최대 100개까지 주제별 도서 데이터를 가져오는 함수 정의 ]
def fetch_books_by_topic(topic, max_results=100):
    # 알라딘 API는 한 번에(한 페이지에) 최대 50개까지만 응답하므로,
    # Start 파라미터를 바꿔가며 여러 번 요청해서 중복 없이 모아준다.
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
        response = requests.get(ALADIN_SEARCH_URL, params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get('item', [])

        if not items:
            break  # 더 이상 가져올 데이터가 없으면 중단

        for item in items:
            # isbn13(없으면 itemId)으로 중복 여부 판단
            unique_id = item.get('isbn13') or item.get('itemId')
            if unique_id in seen_ids:
                continue
            seen_ids.add(unique_id)
            all_items.append(item)
            if len(all_items) >= max_results:
                break

        start += page_size

    return all_items[:max_results]


# 3. '인공지능' 도서 데이터를 처리하는 함수 정의
def process_ai_books():
    # 3.1 [ '인공지능' 관련 도서 검색 ]
    # fetch_books_by_topic()을 호출하여 '인공지능' 관련 도서를 100개 수집합니다.
    books = fetch_books_by_topic('인공지능', 100)

    # 3.2 [ 수집된 데이터에서 가격 정보가 있는 책 필터링 및 가격순 정렬 ]
    priced_books = [b for b in books if b.get('priceStandard')]
    priced_books.sort(key=lambda b: b['priceStandard'], reverse=True)

    # 3.3 [ 상위 10개 도서 선택 ]
    top10 = priced_books[:10]

    # 3.4 [ 상위 10개 도서 정보 출력 ]
    print("가격이 높은 순서대로 상위 10개 도서:")
    for i, book in enumerate(top10, 1):
        print(f"{i}. 제목: {book.get('title')}, 가격: {book.get('priceStandard')}원")

    # 3.5 [ JSON 파일로 저장할 데이터 준비 ]
    # output/ai_top10_books.json 파일로 저장
    # 요구사항: "제목과 저자 정보를 요약하여" 저장 -> 한글 키(제목/저자)만 저장
    result = [
        {
            '제목': b.get('title', ''),
            '저자': b.get('author', ''),
        }
        for b in top10
    ]

    output_folder = Path(__file__).resolve().parent / 'output'
    output_folder.mkdir(parents=True, exist_ok=True)
    with open(output_folder / 'ai_top10_books.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 3.6 [ 완료 메시지를 출력 ]
    print("'ai_top10_books.json' 파일이 생성되었습니다.")

# 함수 실행
if __name__ == '__main__':
    process_ai_books()
