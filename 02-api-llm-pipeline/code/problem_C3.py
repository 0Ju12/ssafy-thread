import os
import requests
from pathlib import Path
from gtts import gTTS
from dotenv import load_dotenv
from openai import OpenAI


# 1. [ 환경 변수 로드 ]
load_dotenv()

MY_TTBKEY = os.getenv('ALADIN_TTBKEY')
GMS_KEY = os.getenv('GMS_KEY')

ALADIN_SEARCH_URL = 'http://www.aladin.co.kr/ttb/api/ItemSearch.aspx'


# GMS 서버를 통해 OpenAI API 사용
client = OpenAI(
    api_key=GMS_KEY,
    base_url="https://gms.ssafy.io/gmsapi/api.openai.com/v1"
)


# 2. [ 최대 100개까지 주제별 도서 데이터를 가져오는 함수 정의 ]
def fetch_books_by_topic(topic, max_results=100):

    # 알라딘 API는 한 번에 최대 50개까지만 응답
    page_size = 50

    all_items = []
    seen_ids = set()
    start = 1

    while len(all_items) < max_results:

        params = {
            'TTBKey': MY_TTBKEY,
            'Query': topic,
            'QueryType': 'Keyword',
            'MaxResults': min(page_size, max_results),
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

        # 알라딘 API 오류 확인
        if 'errorCode' in data:
            print("알라딘 API 오류:")
            print(data)
            break

        items = data.get('item', [])

        if not items:
            break

        for item in items:

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

        # 다음 페이지
        start += 1

    return all_items[:max_results]


# 3. [ GMS를 이용하여 도서 정보를 요약하는 함수 정의 ]
def summarize_book_with_gms(book):

    title = book.get('title', '제목 없음')
    author = book.get('author', '저자 정보 없음')
    description = (
        book.get('description')
        or '소개 정보 없음'
    ).strip()

    conversation_history = [
        {
            "role": "developer",
            "content": (
                "당신은 책을 쉽고 자연스럽게 소개하는 전문 사서입니다. "
                "주어진 책의 제목, 저자, 소개를 바탕으로 "
                "한국어로 2~3문장 정도의 짧고 자연스러운 소개문을 작성하세요."
            )
        },
        {
            "role": "user",
            "content": (
                f"제목: {title}\n"
                f"저자: {author}\n"
                f"책 소개: {description}\n\n"
                "이 책을 음성으로 들었을 때 자연스럽도록 "
                "간단하게 소개해주세요."
            )
        }
    ]

    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=conversation_history
    )

    summary = response.choices[0].message.content

    return summary.strip()


# 4. [ 도서 정보를 텍스트 파일로 저장하는 함수 정의 ]
# 책 정보를 "제목, 저자, GMS 요약" 형식으로 변환하여 txt 파일로 저장
def save_books_info(books, filename):

    lines = []

    for book in books:

        title = book.get(
            'title',
            '제목 없음'
        )

        author = book.get(
            'author',
            '저자 정보 없음'
        )

        # GMS를 이용해 책 소개 요약
        summary = summarize_book_with_gms(book)

        lines.append(
            f"제목: {title}"
        )

        lines.append(
            f"저자: {author}"
        )

        lines.append(
            f"소개: {summary}"
        )

        lines.append(
            '-' * 40
        )

    path = Path(filename)

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        '\n'.join(lines),
        encoding='utf-8'
    )

    print(
        f"{filename} 파일이 생성되었습니다."
    )


# 5. [ 텍스트 파일을 오디오 파일로 변환하는 함수 정의 ]
def create_audio_file(text_file, audio_file):

    text = Path(
        text_file
    ).read_text(
        encoding='utf-8'
    )

    Path(
        audio_file
    ).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    tts = gTTS(
        text=text,
        lang='ko'
    )

    tts.save(
        audio_file
    )

    print(
        f"{audio_file} 파일이 생성되었습니다."
    )


# 6. [ 음악 관련 도서 데이터를 처리하는 함수 정의 ]
def process_music_books():

    # 스크립트 파일이 있는 위치를 기준으로 output 폴더 지정
    base_dir = Path(
        __file__
    ).resolve().parent

    text_path = (
        base_dir
        / 'output'
        / 'music_books_info.txt'
    )

    audio_path = (
        base_dir
        / 'output'
        / 'music_books.mp3'
    )

    # 6.1 [ '음악' 주제의 도서 데이터 수집 ]
    books = fetch_books_by_topic(
        '음악',
        10
    )

    print(
        f"검색된 도서 수: {len(books)}권"
    )

    # 검색 결과가 없으면 종료
    if not books:

        print(
            "알라딘 API에서 검색된 도서가 없습니다."
        )

        return

    # 6.2 [ 도서 정보를 텍스트 파일로 저장 ]
    # 내부에서 GMS를 이용해 도서 소개 요약
    save_books_info(
        books,
        str(text_path)
    )

    # 6.3 [ 텍스트 파일을 오디오 파일로 변환 ]
    create_audio_file(
        str(text_path),
        str(audio_path)
    )

    print(
        "모든 작업이 완료되었습니다."
    )


# 함수 실행
if __name__ == '__main__':
    process_music_books()