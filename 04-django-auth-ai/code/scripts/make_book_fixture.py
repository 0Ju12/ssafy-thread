"""관통 프로젝트 1회차 알라딘 데이터셋(books_2000.json)에서 샘플 도서를 골라 Django fixture 로 변환

사용법 : python scripts/make_book_fixture.py ../../pjt_01/skeleton/data/books_2000.json books/fixtures/books.json
"""
import html, json, re, sys
src, dst = sys.argv[1], sys.argv[2]
items = json.load(open(src, encoding='utf-8'))
by_title = {}
for i in items:
    by_title.setdefault(i['title'], i)

# 저자가 위키피디아에서 검색될 만한 도서 위주로, 분야가 골고루 섞이게 선정 (목록 화면에는 아래쪽이 먼저 보임)
PICKS = [
    '자전거여행 1', '호랑이를 덫에 가두면', '초판본 사슴', '학교에 간 사자', '여행의 이유',
    '정재승의 과학 콘서트', '미로장의 참극', '너와 함께라면 인생도 여행이다', '에드워드 툴레인의 신기한 여행',
    '은하수를 여행하는 히치하이커를 위한 안내서', '시를 잊은 그대에게', '그리고 아무도 없었다',
    '유현준의 인문 건축 기행', '서양미술사', '꾸뻬 씨의 행복 여행', '사자왕 형제의 모험',
    '당신을 알기 전에는 시 없이도 잘 지냈습니다', '푸른 사자 와니니', '초판본 하늘과 바람과 별과 詩',
    '지적 대화를 위한 넓고 얕은 지식 무한', '최소한의 한국사', '물고기는 존재하지 않는다',
    '문과 남자의 과학 공부', '서랍에 저녁을 넣어 두었다',
]

def find(prefix):
    for title, item in by_title.items():
        if title.startswith(prefix):
            return item
    raise SystemExit(f'not found: {prefix}')

def main_title(t):
    # '여행의 이유 (개정증보판) - 부제' -> '여행의 이유'  (부제 · 판 표기 제거)
    t = t.split(' - ')[0].strip()
    return re.sub(r'\s*\((?:[^()]*(?:판|리커버|에디션|양장))\)\s*$', '', t).strip()

def main_author(a):
    # '한강 (지은이), 홍길동 (옮긴이)' -> '한강'
    return re.sub(r'\s*\(.*?\)', '', a.split(',')[0]).strip()

out = []
for pk, prefix in enumerate(PICKS, start=1):
    i = find(prefix)
    out.append({
        'model': 'books.book',
        'pk': pk,
        'fields': {
            'title': main_title(html.unescape(i['title']))[:100],
            'description': html.unescape(i['description']).strip(),
            'customer_review_rank': int(i['customerReviewRank']),
            'author': main_author(html.unescape(i['author']))[:100],
            'author_info': '', 'author_works': '', 'author_image': '',
            'created_at': f'2026-10-29T00:00:{pk:02d}Z',
            'updated_at': f'2026-10-29T00:00:{pk:02d}Z',
        },
    })
json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
for o in out:
    f = o['fields']; print(o['pk'], f['customer_review_rank'], '|', f['title'], '|', f['author'], '|', len(f['description']))
