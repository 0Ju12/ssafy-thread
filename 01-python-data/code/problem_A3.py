import json  # JSON 데이터를 처리하기 위한 라이브러리
from pathlib import Path  # 파일 경로 처리를 위한 라이브러리

# 1. 파일 경로 설정
# pathlib을 사용하여 파일 경로를 설정합니다.
file_path = Path('C:/Users/SSAFY/Desktop/pjt/pjt_01/skeleton/data/books_20.json')  # JSON 파일 경로 설정

# 2. 파일 존재 여부 확인
# 파일이 존재하는지 확인하고, 존재하면 파일을 열어 JSON 데이터를 읽습니다.
if file_path.exists():  # 파일이 존재할 경우
    # 파일 열기
    with file_path.open('r', encoding='utf-8') as file:
        data = json.load(file)

    # 3. 고객 리뷰 순위 리스트 생성
    # 'item' 리스트의 각 항목을 순회하며 'customerReviewRank' 값을 추출하여 리스트에 추가합니다.
    customer_review_ranks = []  # 고객 리뷰 순위를 저장할 빈 리스트
    for item in data['item']:  # 'item' 리스트의 각 항목을 순회
       customer_review_ranks.append(item['customerReviewRank'])

    # 4. 평균 고객 리뷰 순위 계산
    # 고객 리뷰 순위 리스트의 평균을 계산합니다.
    average_review_rank =  (sum(customer_review_ranks) / len(customer_review_ranks))

    # 5. 결과 출력
    # 계산된 평균 고객 리뷰 순위를 출력합니다.
    print(f"도서의 평균 고객 리뷰 순위: {average_review_rank:.2f}")

else:
    # 6. 파일이 없을 경우 처리
    # 파일이 존재하지 않으면 오류 메시지를 출력합니다.
    print(f"파일이 존재하지 않습니다: {file_path}")
