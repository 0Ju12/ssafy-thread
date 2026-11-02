import json  # JSON 데이터를 처리하기 위한 라이브러리
from pathlib import Path  # 파일 경로 처리를 위한 라이브러리

# 1. 파일 경로 설정
# pathlib을 사용하여 파일 경로를 설정합니다.
file_path = Path('C:/Users/SSAFY/Desktop/pjt/pjt_01/skeleton/data/books_20.json')   # JSON 파일 경로 설정

# 2. 파일 존재 여부 확인
# 파일이 존재하는지 확인하고, 존재하면 파일을 열어 JSON 데이터를 읽습니다.
if file_path.exists():  # 파일이 존재할 경우
    # 파일 열기
    with file_path.open('r', encoding='utf-8') as file:
        data = json.load(file)

    # 3. 도서 별 작가 딕셔너리 생성
    # 'item' 리스트의 각 항목에서 책 제목과 작가 이름을 추출하여 딕셔너리에 저장합니다.
    book_authors = {}  # 도서 제목과 작가를 저장할 빈 딕셔너리
    for item in data['item']:  # 'item' 리스트의 각 항목을 순회
        book_authors[item['title']] = item['author']

    # 4. 결과 출력
    # 도서 제목과 작가를 출력합니다.
    print("도서 별 작가 리스트:")
    for title, author in book_authors.items():  # 딕셔너리의 각 항목 순회
        print(f"제목: {title}\n작가: {author}\n")
else:
    # 5. 파일이 없을 경우 처리
    # 파일이 존재하지 않으면 오류 메시지를 출력합니다.
    print(f"파일이 존재하지 않습니다: {file_path}")
