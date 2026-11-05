from django.shortcuts import render,redirect,get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods,require_POST,require_GET
from .models import Book,Thread,Comment,Category
from .forms import BookForm,ThreadForm,CommentForm
from .services import enrich_author,generate_cover
from .aladin import search_books, AladinError
from .aladin_signing import make_token, read_token
@require_GET
def index(request):
    books=Book.objects.select_related('user','category').order_by('-created_at')
    selected=request.GET.get('category','')
    if selected.isdigit():books=books.filter(category_id=int(selected))
    q=request.GET.get('q','').strip()
    if q:books=books.filter(title__icontains=q)
    return render(request,'books/index.html',{'books':books,'categories':Category.objects.all(),'selected':selected,'q':q})
@require_http_methods(['GET','POST'])
@login_required
def create(request):
    form=BookForm(request.POST or None)
    selected = read_token(request.POST.get('aladin_token', '')) if request.method == 'POST' and request.POST.get('aladin_token') else None
    if request.method=='POST' and request.POST.get('aladin_token') and selected is None:
        form.add_error(None, '알라딘 도서 선택 정보가 만료되었거나 변경되었습니다. 다시 검색해 주세요.')
    if request.method=='POST' and form.is_valid() and (not request.POST.get('aladin_token') or selected is not None):
        book=form.save(commit=False);book.user=request.user
        if selected and book.title==selected['title'] and book.author==selected['author']:
            book.aladin_isbn13 = str(selected.get('isbn13') or '')[:13]
            book.aladin_cover_url = str(selected.get('cover') or '')[:500]
            book.aladin_publisher = str(selected.get('publisher') or '')[:200]
            book.aladin_pub_date = str(selected.get('pub_date') or '')[:30]
        book.save()
        if request.POST.get('ai_author')=='on' and not enrich_author(book):messages.warning(request,'AI 작가 정보를 가져오지 못했습니다. API 키·네트워크 상태를 확인해 주세요.')
        return redirect('books:detail',book.pk)
    return render(request,'books/form.html',{'form':form,'heading':'도서 등록','ai_author':True,'aladin_search_link':True,'aladin_token':request.POST.get('aladin_token','') if request.method=='POST' else ''})
@require_GET
def detail(request,pk):
    book=get_object_or_404(Book.objects.select_related('user','category'),pk=pk)
    return render(request,'books/detail.html',{'book':book,'threads':book.threads.select_related('user').order_by('-created_at')})
@require_http_methods(['GET','POST'])
@login_required
def update(request,pk):
    book=get_object_or_404(Book,pk=pk,user=request.user)
    form=BookForm(request.POST or None,instance=book)
    if request.method=='POST' and form.is_valid():form.save();return redirect('books:detail',pk)
    return render(request,'books/form.html',{'form':form,'heading':'도서 수정'})
@require_POST
@login_required
def delete(request,pk):
    book=get_object_or_404(Book,pk=pk,user=request.user);book.delete();return redirect('books:index')
@require_http_methods(['GET','POST'])
@login_required
def thread_create(request,pk):
    book=get_object_or_404(Book,pk=pk)
    form=ThreadForm(request.POST or None,request.FILES or None)
    if request.method=='POST' and form.is_valid():
        thread=form.save(commit=False);thread.user=request.user;thread.book=book;thread.save()
        if request.POST.get('ai_cover')=='on' and not thread.cover_image and not generate_cover(thread):messages.warning(request,'AI 커버 이미지를 생성하지 못했습니다. API 키·네트워크 상태를 확인해 주세요.')
        return redirect('books:thread_detail',thread.pk)
    return render(request,'books/form.html',{'form':form,'heading':'쓰레드 작성','book':book,'ai_cover':True})
@require_GET
def thread_detail(request,pk):
    thread=get_object_or_404(Thread.objects.select_related('user','book'),pk=pk)
    return render(request,'books/thread_detail.html',{'thread':thread,'comments':thread.comments.select_related('user').order_by('-created_at'),'comment_form':CommentForm()})
@require_http_methods(['GET','POST'])
@login_required
def thread_update(request,pk):
    thread=get_object_or_404(Thread,pk=pk,user=request.user)
    form=ThreadForm(request.POST or None,request.FILES or None,instance=thread)
    if request.method=='POST' and form.is_valid():form.save();return redirect('books:thread_detail',pk)
    return render(request,'books/form.html',{'form':form,'heading':'쓰레드 수정'})
@require_POST
@login_required
def thread_delete(request,pk):
    thread=get_object_or_404(Thread,pk=pk,user=request.user);book_pk=thread.book_id;thread.delete();return redirect('books:detail',book_pk)
@require_POST
@login_required
def like(request,pk):
    thread=get_object_or_404(Thread,pk=pk)
    if thread.likes.filter(pk=request.user.pk).exists():thread.likes.remove(request.user)
    else:thread.likes.add(request.user)
    return redirect('books:thread_detail',pk)
@require_POST
@login_required
def comment_create(request,pk):
    thread=get_object_or_404(Thread,pk=pk);form=CommentForm(request.POST)
    if form.is_valid():comment=form.save(commit=False);comment.user=request.user;comment.thread=thread;comment.save()
    return redirect('books:thread_detail',pk)
@require_POST
@login_required
def comment_delete(request,pk):
    comment=get_object_or_404(Comment,pk=pk,user=request.user);thread_pk=comment.thread_id;comment.delete();return redirect('books:thread_detail',thread_pk)

@require_http_methods(['GET', 'POST'])
@login_required
def aladin_search(request):
    """Search external metadata, then allow a deliberate, validated import into BookForm."""
    results = []
    keyword = (request.GET.get('q', '') if request.method == 'GET' else request.POST.get('q', '')).strip()
    if keyword:
        try:
            results = search_books(keyword)
            for book in results:
                book['token'] = make_token(book)
        except AladinError as exc:
            messages.warning(request, str(exc))
    return render(request, 'books/aladin_search.html', {'q': keyword, 'results': results})

@require_POST
@login_required
def aladin_select(request):
    selected = read_token(request.POST.get('token', ''))
    if not selected:
        messages.error(request, '도서 선택 정보가 만료되었습니다. 다시 검색해 주세요.')
        return redirect('books:aladin_search')
    # Selection prefills a model form; the user chooses rating/category before saving.
    form = BookForm(initial={
        'title': selected.get('title', ''), 'author': selected.get('author', ''),
        'description': selected.get('description') or '도서 소개를 입력해 주세요.',
    })
    return render(request, 'books/form.html', {
        'form': form, 'heading': '알라딘 도서 정보로 등록', 'ai_author': True,
        'aladin_search_link': True, 'aladin_token': request.POST.get('token', ''),
        'aladin_cover_preview': selected.get('cover', ''),
    })
