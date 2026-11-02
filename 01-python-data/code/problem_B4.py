from datetime import datetime  # 날짜와 시간 처리를 위한 라이브러리
import json  # JSON 데이터를 처리하기 위한 라이브러리
from pathlib import Path  # 파일 경로 처리를 위한 라이브러리

# 1. 파일 경로 설정 (books_500.json 사용)
file_path = Path('C:/Users/SSAFY/Desktop/pjt/pjt_01/skeleton/data/books_500.json')


# 파일 존재 여부 확인
if file_path.exists():  # 파일이 존재할 경우
    # 2. 파일 열기
    with file_path.open('r', encoding='utf-8') as file:
        books = json.load(file)

    latest_books = sorted(
        books,
        key=lambda book: book['pubDate'],
        reverse=True
    )[:10]

    # 4. 결과 출력
    print("최신 도서 10개:")
    for book in latest_books:  # 선택된 도서를 순회하며 출력
        print(f"{book['title']} - {book['pubDate']}")

else:
    print(f"파일이 존재하지 않습니다: {file_path}")
