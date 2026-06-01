from django.urls import path
from . import api_views

urlpatterns = [
    # Filter-bar dropdowns (quiz start bar)
    path('topics/', api_views.topics_fragment, name='api_topics'),
    path('subtopics/', api_views.subtopics_fragment, name='api_subtopics'),
    # Browse card grid (HTML fragments)
    path('browse/topics/', api_views.browse_topics, name='api_browse_topics'),
    path('browse/subtopics/', api_views.browse_subtopics, name='api_browse_subtopics'),
    # JSON APIs for quiz panel
    path('browse/topics/json/', api_views.browse_topics_json, name='api_browse_topics_json'),
    path('browse/subtopics/json/', api_views.browse_subtopics_json, name='api_browse_subtopics_json'),
    # Syllabus JSON APIs
    path('syllabuses/', api_views.syllabuses_json, name='api_syllabuses'),
    path('syllabus-courses/', api_views.syllabus_courses_json, name='api_syllabus_courses'),
]
