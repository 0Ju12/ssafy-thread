from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('books/', include('books.urls')),
    # 홈페이지 : 루트 주소로 들어오면 도서 목록(books:index)으로 이동
    path('', RedirectView.as_view(pattern_name='books:index'), name='home'),
]
