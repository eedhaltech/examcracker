from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .models import Course, Topic, SubTopic, Syllabus


def home(request):
    if not request.user.is_authenticated and not settings.DEBUG:
        login_url = reverse('account_login')
        return redirect(f'{login_url}?next={request.path}')

    # Always fetch fresh — cache is cleared by panel on any change
    syllabuses = list(
        Syllabus.objects.prefetch_related(
            'courses__topics__subtopics'
        ).order_by('order', 'name')
    )
    courses = list(
        Course.objects.select_related('syllabus').prefetch_related(
            'topics__subtopics'
        ).order_by('order', 'name')
    )
    return render(request, 'questions/home.html', {
        'syllabuses': syllabuses,
        'courses': courses,
    })


@login_required
def course_index(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    topics = Topic.objects.filter(course=course).prefetch_related('subtopics').order_by('order', 'name')
    return render(request, 'questions/course_index.html', {
        'course': course,
        'topics': topics,
    })


@login_required
def topic_index(request, course_slug, topic_slug):
    course = get_object_or_404(Course, slug=course_slug)
    topic = get_object_or_404(Topic, slug=topic_slug, course=course)
    subtopics = SubTopic.objects.filter(topic=topic).order_by('order', 'name')
    return render(request, 'questions/topic_index.html', {
        'course': course,
        'topic': topic,
        'subtopics': subtopics,
    })


@login_required
def subtopic_index(request, course_slug, topic_slug, subtopic_slug):
    course = get_object_or_404(Course, slug=course_slug)
    topic = get_object_or_404(Topic, slug=topic_slug, course=course)
    subtopic = get_object_or_404(SubTopic, slug=subtopic_slug, topic=topic)
    question_count = subtopic.questions.count()
    return render(request, 'questions/subtopic_index.html', {
        'course': course,
        'topic': topic,
        'subtopic': subtopic,
        'question_count': question_count,
    })
