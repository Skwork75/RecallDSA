from django.urls import path
from . import views

urlpatterns = [
    path('home/', views.home, name='home'),
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),
    path('auth/logout/', views.logout, name='logout'),
    path('auth/me/', views.current_user, name='current-user'),
    path('auth/profile/', views.profile, name='profile'),
    path('revisions/today/', views.today_revisions, name='today-revisions'),
    path('assessments/weekly/', views.weekly_assessment, name='weekly-assessment'),
    path('problems/<int:problem_id>/solve/', views.mark_problem_solved, name='mark-problem-solved'),
]