from django.urls import path, re_path
from . import views

app_name='market'
urlpatterns=[
    path('', views.dashboard, name='dashboard'),
    path('refresh/', views.refresh, name='refresh'),
    path('stocks/', views.stock_search, name='search'),
    re_path(r'^stocks/(?P<code>\d{6})/$', views.stock_detail, name='stock_detail'),
]
