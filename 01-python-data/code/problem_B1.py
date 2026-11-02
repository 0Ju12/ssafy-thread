import json  # JSON 파일을 처리하기 위한 라이브러리
from pathlib import Path  # 파일 경로를 처리하기 위한 라이브러리

# 1. 파일 경로 설정 (books_500.json 사용)
file_path = Path('C:/Users/SSAFY/Desktop/pjt/pjt_01/skeleton/data/books_500.json')

# 2. 파일 존재 여부 확인
# 파일이 존재하는지 확인하고, 존재하면 파일을 열어 JSON 데이터를 읽습니다.
if file_path.exists():  # 파일 존재 여부 확인
    # 파일 열기
    with file_path.open('r', encoding='utf-8') as file:
        books = json.load(file)

    # 3. 어린이 도서가 아닌 책 필터링
    non_children_books = []  # 어린이 도서가 아닌 책을 저장할 리스트
    for book in books:
        if '어린이' not in book['categoryName']:
            non_children_books.append(book)



    # 4. 결과 출력
    print("어린이 도서가 아닌 책 목록:")
    for book in non_children_books:
        print(f"{book['title']}, {book['categoryName']}")
else:
    print(f"파일이 존재하지 않습니다: {file_path}")


