from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from .ai import AIError, AuthorInfoError, analyze_book, generate_author_profile
from .forms import BookForm
from .models import Book


def fill_author_profile(request, book):
    """F417 : AI 로 작가 정보를 생성해 book 에 저장 (실패해도 도서 저장은 유지하고 경고만 표시)"""
    try:
        profile = generate_author_profile(book.author, book.title, book.description)
    except AuthorInfoError as error:
        messages.warning(request, str(error))
        return
    book.author_info = profile['author_info']
    book.author_works = profile['author_works']
    book.author_image = profile['author_image']
    book.save(update_fields=['author_info', 'author_works', 'author_image', 'updated_at'])


@require_safe
def index(request):
    """F412 전체 도서 조회"""
    books = Book.objects.order_by('-pk')
    context = {'books': books}
    return render(request, 'books/index.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def create(request):
    """F413 도서 생성 : 로그인한 사용자만"""
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save()
            fill_author_profile(request, book)  # F417 심화
            messages.success(request, f"'{book.title}' 도서를 등록했습니다.")
            return redirect('books:detail', book.pk)
    else:
        form = BookForm()
    context = {'form': form}
    return render(request, 'books/create.html', context)


@require_safe
def detail(request, pk):
    """F414 단일 도서 조회"""
    book = get_object_or_404(Book, pk=pk)
    context = {'book': book}
    return render(request, 'books/detail.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def update(request, pk):
    """F415 도서 수정 : 로그인한 사용자만, 기존 데이터가 미리 입력된 폼"""
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        old_author = book.author
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            book = form.save()
            # 저자가 바뀌었으면 작가 정보도 새로 생성
            if book.author != old_author:
                fill_author_profile(request, book)
            messages.success(request, '도서 정보를 수정했습니다.')
            return redirect('books:detail', book.pk)
    else:
        form = BookForm(instance=book)
    context = {'form': form, 'book': book}
    return render(request, 'books/update.html', context)


@login_required
@require_POST
def delete(request, pk):
    """F416 도서 삭제 : 로그인한 사용자만, POST 요청만"""
    book = get_object_or_404(Book, pk=pk)
    book.delete()
    messages.info(request, f"'{book.title}' 도서를 삭제했습니다.")
    return redirect('books:index')


@login_required
@require_POST
def regenerate_author(request, pk):
    """F417 보조 기능 : 작가 정보 다시 생성 (처음 생성에 실패했을 때 사용)"""
    book = get_object_or_404(Book, pk=pk)
    fill_author_profile(request, book)
    return redirect('books:detail', book.pk)


@login_required
@require_POST
def analyze(request, pk):
    """추가 기능 : AI 도서 분석 (한 줄 요약 · 키워드 · 추천 독자 · 감상 포인트)"""
    book = get_object_or_404(Book, pk=pk)
    try:
        book.ai_analysis = analyze_book(book)
    except AIError as error:
        messages.warning(request, str(error))
    else:
        book.save(update_fields=['ai_analysis', 'updated_at'])
        messages.success(request, 'AI 도서 분석을 완료했습니다.')
    return redirect('books:detail', book.pk)
