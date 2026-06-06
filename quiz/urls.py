from django.urls import path
from . import views

urlpatterns = [
    path('start/<slug:subtopic_slug>/', views.start_quiz, name='start_quiz'),
    path('start-scoped/', views.start_quiz_scoped, name='start_quiz_scoped'),
    path('session-scoped/', views.quiz_session_scoped, name='quiz_session_scoped'),
    path('session/<int:attempt_id>/', views.quiz_session, name='quiz_session'),
    path('save-answer/<int:attempt_id>/', views.save_answer, name='save_answer'),
    path('submit/<int:attempt_id>/', views.submit_quiz, name='submit_quiz'),
    path('results/<int:attempt_id>/', views.quiz_results, name='quiz_results'),
    path('level-preference/<int:attempt_id>/', views.set_level_preference, name='set_level_preference'),
]
