from django.urls import path
from . import views

urlpatterns = [
    path('home/', views.home, name='home'),
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),
    path('auth/logout/', views.logout, name='logout'),
    path('auth/me/', views.current_user, name='current-user'),
    path('auth/profile/', views.profile, name='profile'),
    path('problems/<int:problem_id>/solve/', views.mark_problem_solved, name='mark-problem-solved'),
]