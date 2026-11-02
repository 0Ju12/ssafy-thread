import json  # JSON 파일을 처리하기 위한 라이브러리
from pathlib import Path  # 파일 경로를 처리하기 위한 라이브러리

# 1. 파일 경로 설정 (books_500.json 사용)
file_path = Path('C:/Users/SSAFY/Desktop/pjt/pjt_01/skeleton/data/books_500.json')


# 파일 존재 여부 확인
if file_path.exists():  # 파일이 존재할 경우
    # 2. 파일 열기
    with file_path.open('r', encoding='utf-8') as file:
        books = json.load(file)

    # 3. 카테고리별 통계 집계
    category_stats = {}  # 카테고리별 통계를 저장할 딕셔너리

    for book in books:
        category = book['categoryName']
        price = book['priceStandard']
        if category in category_stats:
            category_stats[category]['count'] += 1
            category_stats[category]['total_price'] += price
        else:
            category_stats[category] = {
                'count': 1,
                'total_price': price
                }

    # 4. 결과 출력
    print("카테고리별 도서 통계:")
    for category, stats in category_stats.items():
        average = stats['total_price'] / stats['count']
        print(f"{category}: {stats['count']}권, 평균 가격 {average:.2f}원")

    
else:
    print(f"파일이 존재하지 않습니다: {file_path}")
