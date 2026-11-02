from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from books.ai import AIError, recommend_books
from books.models import Book

from .forms import (
    CustomAuthenticationForm,
    CustomPasswordChangeForm,
    CustomUserChangeForm,
    CustomUserCreationForm,
)


@require_http_methods(['GET', 'POST'])
def login(request):
    """F406 로그인 : GET 이면 로그인 화면, POST 이면 검증 후 세션 생성"""
    # 이미 로그인한 사용자는 로그인 화면을 볼 필요가 없음
    if request.user.is_authenticated:
        return redirect('books:index')

    if request.method == 'POST':
        # AuthenticationForm 은 첫 번째 인자로 request 를 받음 (다른 폼과 순서가 다름)
        form = CustomAuthenticationForm(request, request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            messages.success(request, f'{form.get_user().username}님, 환영합니다.')
            # @login_required 가 붙여 준 ?next= 주소가 우리 사이트 주소일 때만 그곳으로 이동
            # (검사 없이 이동하면 외부 사이트로 보내는 오픈 리다이렉트 공격이 가능)
            next_url = request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)
            return redirect('books:index')
    else:
        form = CustomAuthenticationForm()
    context = {'form': form}
    return render(request, 'accounts/login.html', context)


@require_POST
def logout(request):
    """F407 로그아웃 : 링크(GET)로는 로그아웃되지 않도록 POST 요청만 허용"""
    if request.user.is_authenticated:
        auth_logout(request)
        messages.info(request, '로그아웃되었습니다.')
    return redirect('books:index')


@require_http_methods(['GET', 'POST'])
def signup(request):
    """F408 회원가입 (+ F418 추가 정보)"""
    if request.user.is_authenticated:
        return redirect('books:index')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # DB 저장을 잠시 미루고 User 객체만 받기
            user = form.save(commit=False)
            # 관심 장르 : ['NOVEL', 'SCIENCE'] -> 'NOVEL,SCIENCE'
            user.interested_genres = ','.join(form.cleaned_data['interested_genres'])
            user.save()
            auth_login(request, user)  # 가입하자마자 로그인 상태로
            messages.success(request, f'{user.username}님, 회원가입을 환영합니다.')
            return redirect('books:index')
    else:
        form = CustomUserCreationForm()
    context = {'form': form}
    return render(request, 'accounts/signup.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def update(request):
    """F409 회원정보 수정 (+ F418 추가 정보)"""
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.interested_genres = ','.join(form.cleaned_data['interested_genres'])
            user.save()
            messages.success(request, '회원정보를 수정했습니다.')
            return redirect('books:index')
    else:
        # DB 의 'NOVEL,SCIENCE' 를 리스트로 바꿔 체크된 상태로 보여 줌
        form = CustomUserChangeForm(
            instance=request.user,
            initial={'interested_genres': request.user.get_genre_list()},
        )
    context = {'form': form}
    return render(request, 'accounts/update.html', context)


@login_required
@require_POST
def delete(request):
    """F410 회원탈퇴 : POST 요청만 허용"""
    # 순서 주의 : 회원을 먼저 지운 뒤 세션을 정리(로그아웃)
    request.user.delete()
    auth_logout(request)
    messages.info(request, '회원탈퇴가 완료되었습니다.')
    return redirect('books:index')


@login_required
@require_http_methods(['GET', 'POST'])
def change_password(request):
    """F411 비밀번호 변경 : 변경 후에도 로그인 상태 유지"""
    if request.method == 'POST':
        # PasswordChangeForm 은 첫 번째 인자로 "누구의" 비밀번호인지(user) 를 받음
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # 세션을 새 비밀번호 기준으로 갱신 => 강제 로그아웃 방지
            update_session_auth_hash(request, user)
            messages.success(request, '비밀번호를 변경했습니다.')
            return redirect('books:index')
    else:
        form = CustomPasswordChangeForm(request.user)
    context = {'form': form}
    return render(request, 'accounts/change_password.html', context)


@login_required
@require_safe
def profile(request, username):
    """F419 개인 프로필 페이지"""
    # get_user_model() : settings.AUTH_USER_MODEL 에 지정된 User 를 돌려줌
    User = get_user_model()
    user_profile = get_object_or_404(User, username=username)
    # 템플릿의 {{ user }} 는 로그인한 사람이므로, 조회한 회원은 'user_profile' 로 넘김
    context = {'user_profile': user_profile}

    # 추가 기능 : 본인 프로필이면 세션에 저장해 둔 AI 맞춤 추천 결과를 함께 보여 줌
    if request.user == user_profile:
        saved = request.session.get('recommendations', [])
        # 추천 이후 삭제된 도서는 제외
        existing = set(Book.objects.filter(pk__in=[r['id'] for r in saved]).values_list('pk', flat=True))
        context['recommendations'] = [r for r in saved if r['id'] in existing]
    return render(request, 'accounts/profile.html', context)


@login_required
@require_POST
def recommend(request):
    """추가 기능 : AI 맞춤 도서 추천 (관심 장르 · 독서 습관 기반, 등록된 도서 중에서만 추천)"""
    try:
        results = recommend_books(request.user, Book.objects.order_by('pk'))
    except AIError as error:
        messages.warning(request, str(error))
    else:
        # 새로고침해도 다시 호출하지 않도록 세션에 저장 (POST → 리다이렉트 → GET)
        request.session['recommendations'] = results
        messages.success(request, f'AI 가 {len(results)}권을 추천했습니다.')
    return redirect('accounts:profile', request.user.username)
