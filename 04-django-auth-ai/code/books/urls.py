from django.urls import path

from . import views

# app_name + name 으로 URL 을 이름으로 참조 (NF401) : {% url 'books:detail' book.pk %}
app_name = 'books'
urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.create, name='create'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/update/', views.update, name='update'),
    path('<int:pk>/delete/', views.delete, name='delete'),
    path('<int:pk>/author/', views.regenerate_author, name='regenerate_author'),
    path('<int:pk>/analyze/', views.analyze, name='analyze'),
]
