from django.urls import path

from . import views

# app_name + name 으로 URL 을 이름으로 참조 (NF401) : {% url 'accounts:login' %}
app_name = 'accounts'
urlpatterns = [
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('update/', views.update, name='update'),
    path('delete/', views.delete, name='delete'),
    path('password/', views.change_password, name='change_password'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('recommend/', views.recommend, name='recommend'),
]
