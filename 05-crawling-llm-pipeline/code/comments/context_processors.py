from django.conf import settings

# 디자인 테마 (CSS 파일 이름 : 표시 이름)
THEMES = {
    'clean': 'A 클린 증권',
    'board': 'B 시세 전광판',
    'proof': 'C 교정지',
    'chat': 'D 커뮤니티 대화형',
    'desk': 'E 분석 워크스페이스',
    'story': 'F 카드뉴스 스토리',
    'aurora': 'G 오로라 AI',
    'atelier': 'H 아틀리에 리서치',
    'brutal': 'I 네오 브루탈',
    'glass': 'J 소프트 글래스',
    'console': 'K 터미널 프로',
}

# 결과 화면 구조가 다른 테마. 새 테마는 기존 구조를 활용하며 디자인을 확장합니다.
DETAIL_LAYOUTS = {'chat', 'desk', 'story', 'brutal', 'glass', 'console'}
DETAIL_TEMPLATES = {'brutal': 'detail_story.html', 'glass': 'detail_desk.html', 'console': 'detail_desk.html'}


def ui_theme(request):
    """현재 화면 테마를 템플릿에 전달한다.

    주소에 ?theme=board 처럼 붙이면 그 테마로 바꿔 세션에 기억한다 (디자인 비교용)
    """
    requested = request.GET.get('theme')
    if requested in THEMES and settings.SHOW_THEME_SWITCHER:
        request.session['ui_theme'] = requested

    theme = request.session.get('ui_theme') if settings.SHOW_THEME_SWITCHER else None
    theme = theme or settings.UI_THEME
    if theme not in THEMES:
        theme = 'clean'
    return {
        'ui_theme': theme,
        'ui_themes': THEMES,
        'show_theme_switcher': settings.SHOW_THEME_SWITCHER,
    }
