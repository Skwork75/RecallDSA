from django.urls import path
from . import views

urlpatterns = [
    path('home/', views.home, name='home'),
    path('problems/', views.home, name='global-problems'),
    path('sheets/', views.dsasheets, name='dsasheets'),
    path('sheets/create/', views.create_dsasheet, name='create-dsasheet'),
    path('sheets/<int:sheet_id>/add-problem/', views.add_problem_to_sheet, name='add-problem-to-sheet'),
    path('sheets/<slug:slug>/track-all/', views.track_all_sheet_problems, name='track-all-sheet-problems'),
    path('sheets/<slug:slug>/track-selected/', views.track_selected_sheet_problems, name='track-selected-sheet-problems'),
    path('sheets/<slug:slug>/', views.dsasheet_detail, name='dsasheet-detail'),
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),
    path('auth/logout/', views.logout, name='logout'),
    path('auth/me/', views.current_user, name='current-user'),
    path('auth/profile/', views.profile, name='profile'),
    path('revisions/submit-review/', views.submit_review, name='submit-review'),
    path('revisions/due-today/', views.due_today, name='due-today'),
    path('revisions/today/', views.today_revisions, name='today-revisions'),
    path('assessments/weekly/', views.weekly_assessment, name='weekly-assessment'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('problems/<int:problem_id>/solve/', views.mark_problem_solved, name='mark-problem-solved'),
]