from django.urls import path

from . import views

app_name = 'comments'

urlpatterns = [
    path('', views.index, name='index'),
    path('run/', views.run, name='run'),
    path('run/stream/', views.run_stream, name='run_stream'),
    path('results/<int:pk>/', views.detail, name='detail'),
    path('results/<int:pk>/summary/', views.regenerate_summary, name='summary'),
    path('results/<int:pk>/export/<str:fmt>/', views.export_result, name='export'),
    path('results/<int:pk>/compare/', views.compare_history, name='compare_history'),
]
