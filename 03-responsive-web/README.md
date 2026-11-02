# 관통 3 · ThRead 반응형 웹페이지 (2026.10.15)

HTML · CSS · **Bootstrap 5.3**으로 도서 추천·독서 커뮤니티 서비스 ThRead의 반응형 메인 페이지와 도서 상세 페이지를 구현했습니다.
(정적 UI 과제 — AI 추천·게시글 등은 화면 구성용 예시 데이터)

## 구현 내용
| 영역 | 구현 |
|---|---|
| Navbar · Hero | 로고 색 분리, `navbar-expand-sm` + Collapse 햄버거 메뉴, `position`·`z-index`로 Hero 위 배치 |
| 베스트셀러 | Carousel로 12권을 4권씩 3슬라이드, 자동 전환 · 심화: Hero 하단에 겹치는 오버랩 디자인 |
| AI 추천 | Grid 7:5 배치, 문장 일부 강조 |
| 장르별 목록 | Flexbox·CSS Grid, 576px 미만 1열 · 심화: `grid-column`/`grid-row`로 크기가 다른 동적 그리드 |
| 인기 쓰레드 | Card + `row-cols-1`/`row-cols-sm-3`, Pagination 스타일 |
| 통합 · 상세 | 메인 페이지 통합, 로그아웃 Modal, 도서 상세(Tabs + Google Maps iframe) |

## 어려웠던 점과 해결
- 심화 CSS Grid와 **모바일 1열 조건이 충돌** → 미디어 쿼리 적용 순서와 선택자를 점검해 수정
- 이미지 파일명·확장자 불일치 → 실제 `assets` 경로를 확인해 상대 경로 정리
- 개별 HTML을 하나로 합칠 때 **CSS 충돌** → Bootstrap 클래스와 사용자 CSS의 역할을 구분해 구조 정리

## 배운 것
Bootstrap Navbar·Collapse·Carousel·Card·Pagination·Modal·Tabs · Grid 브레이크포인트 · Flexbox와 CSS Grid의 차이 · `@media` · `object-fit`

## 코드
[`code/`](code) — 컴포넌트별 HTML(`01-navbar` ~ `05-popular_thread`)과 통합 페이지(`06-main`, `07-book-detail`)

> 도서 표지 이미지(`assets/`)는 제공 자료라 포함하지 않았습니다. 브라우저로 열면 레이아웃은 그대로 확인할 수 있고 이미지 자리만 비어 보입니다.
