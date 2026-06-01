from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('<slug:course_slug>/', views.course_index, name='course_index'),
    path('<slug:course_slug>/<slug:topic_slug>/', views.topic_index, name='topic_index'),
    path('<slug:course_slug>/<slug:topic_slug>/<slug:subtopic_slug>/', views.subtopic_index, name='subtopic_index'),
]
