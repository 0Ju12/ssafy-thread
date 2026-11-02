import os                       # 운영 체제와 상호작용하기 위한 라이브러리
import requests                 # HTTP 요청을 보내기 위한 라이브러리
from pathlib import Path        # 파일 경로 처리를 위한 라이브러리
from dotenv import load_dotenv  # 환경 변수 로드를 위한 라이브러리


load_dotenv()  # .env 파일을 읽어 환경 변수로 설정합니다.

# 1. [ dotenv를 활용하여 알라딘 API 키 가져오기 ]
MY_TTBKEY = os.getenv('ALADIN_TTBKEY')
# 2. [ 공식 문서를 참고하여 알라딘 API 검색 URL 설정하기 ]
ALADIN_SEARCH_URL = 'http://www.aladin.co.kr/ttb/api/ItemSearch.aspx'

# 3. 도서 데이터를 가져오는 함수 정의
def fetch_books(keyword):
    url = ALADIN_SEARCH_URL
    params = {
        'TTBKey': MY_TTBKEY,     # API 키
        'Query': keyword,        # 검색 키워드
        'output': 'js',          # 응답 형식
        'Version': '20131101',   # API 버전
    }

    # 3.1 [ requests 문서를 참고하여 HTTP GET 요청 보내는 코드 작성하기 ]
    response = requests.get(url, params=params)
    response.raise_for_status()

    # 3.2 [ requests 문서를 참고하여 응답 데이터를  python의 dict 타입으로 변환하여 data 변수에 저장 ]
    data = response.json()

    return data


# 4. 도서 데이터를 파일로 저장하는 함수 정의
def save_books_to_file(data, file_path):

    # 4.1 [ 도서 데이터 가져오기 ]
    books = data.get('item', [])

    lines = []
    for book in books:
        # 4.2 [ 도서 정보 가공하기기 ]
        # [ 도서 제목, 저자, 출판사, 가격 필드를 각각의 변수로 저장 ]
        title = book.get('title', '제목 없음')
        author = book.get('author', '저자 정보 없음')
        publisher = book.get('publisher', '출판사 정보 없음')
        price = book.get('priceStandard', 0)  # 정가(priceStandard) 사용

        # 가져온 데이터를 lines 리스트에 추가
        lines.append(f'## 제목: {title}, \n * 저자: {author}\n * 출판사: {publisher}, * 가격: {price}원')
        lines.append('---' * 20)    # 구분선

    path = Path(file_path) # 파일 경로 객체 생성
    # 4.3 [ 데이터를 txt 파일로 저장 ]
    path.parent.mkdir(parents=True, exist_ok=True)  # 상위 폴더가 없으면 생성
    path.write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    # '컴퓨터' 키워드를 사용하여 도서 검색 데이터를 가져옵니다.
    books_data = fetch_books('컴퓨터')

    # 5. [ output 폴더 생성 ]
    # 스크립트 파일이 있는 위치를 기준으로 output 폴더를 지정합니다.
    # (터미널을 어느 폴더에서 실행하든, 항상 이 스크립트 옆에 output 폴더가 생깁니다.)
    output_folder = Path(__file__).resolve().parent / 'output'
    output_folder.mkdir(parents=True, exist_ok=True)  # 이미 존재해도 에러 없음

    # 도서 데이터를 파일로 저장
    file_path = output_folder / 'computer_books.txt'    # 저장될 파일명 및 경로로
    save_books_to_file(books_data, file_path)

    # 저장된 파일을 읽어서 콘솔에 출력하기
    saved_data = Path(file_path).read_text(encoding='utf-8')
    print(saved_data)
