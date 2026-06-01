from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.urls import reverse
from .models import Course, Topic, SubTopic, Syllabus


@login_required
def topics_fragment(request):
    """Filter-bar dropdown: topics for a given course."""
    course_id = request.GET.get('course_id')
    topics = Topic.objects.filter(course_id=course_id).order_by('order', 'name') if course_id else []
    html = render_to_string('questions/fragments/topics_options.html', {'topics': topics})
    return HttpResponse(html)


@login_required
def subtopics_fragment(request):
    """Filter-bar dropdown: subtopics for a given topic."""
    topic_id = request.GET.get('topic_id')
    subtopics = SubTopic.objects.filter(topic_id=topic_id).order_by('order', 'name') if topic_id else []
    html = render_to_string('questions/fragments/subtopics_options.html', {'subtopics': subtopics})
    return HttpResponse(html)


@login_required
def browse_topics(request):
    """Browse card grid: topic cards HTML for a selected course."""
    course_id = request.GET.get('course_id')
    if course_id:
        try:
            course = Course.objects.get(pk=course_id)
            topics = list(Topic.objects.filter(course=course).prefetch_related('subtopics').order_by('order', 'name'))
        except Course.DoesNotExist:
            course, topics = None, []
    else:
        course, topics = None, []
    html = render_to_string(
        'questions/fragments/browse_topics.html',
        {'course': course, 'topics': topics},
        request=request,
    )
    return HttpResponse(html)


@login_required
def browse_subtopics(request):
    """Browse card grid: subtopic cards HTML for a selected topic."""
    topic_id = request.GET.get('topic_id')
    if topic_id:
        try:
            topic = Topic.objects.select_related('course').prefetch_related('subtopics').get(pk=topic_id)
            subtopics = list(topic.subtopics.order_by('order', 'name'))
        except Topic.DoesNotExist:
            topic, subtopics = None, []
    else:
        topic, subtopics = None, []
    html = render_to_string(
        'questions/fragments/browse_subtopics.html',
        {'topic': topic, 'subtopics': subtopics},
        request=request,
    )
    return HttpResponse(html)


@login_required
def browse_topics_json(request):
    """Quiz panel + explorer: JSON list of topics for a course."""
    course_id = request.GET.get('course_id')
    if not course_id:
        return JsonResponse({'topics': []})
    topics = Topic.objects.filter(course_id=course_id).prefetch_related('subtopics').order_by('order', 'name')
    data = [
        {
            'id': t.id,
            'name': t.name,
            'slug': t.slug,
            'subtopic_count': t.subtopics.count(),
        }
        for t in topics
    ]
    return JsonResponse({'topics': data})


@login_required
def browse_subtopics_json(request):
    """Quiz panel + explorer: JSON list of subtopics for a topic."""
    topic_id = request.GET.get('topic_id')
    if not topic_id:
        return JsonResponse({'subtopics': []})
    try:
        topic = Topic.objects.select_related('course').get(pk=topic_id)
    except Topic.DoesNotExist:
        return JsonResponse({'subtopics': []})
    subtopics = SubTopic.objects.filter(topic=topic).order_by('order', 'name')
    data = [
        {
            'id': s.id,
            'name': s.name,
            'slug': s.slug,
            'question_count': s.questions.count(),
            'url': reverse('subtopic_index', args=[topic.course.slug, topic.slug, s.slug]),
        }
        for s in subtopics
    ]
    return JsonResponse({'subtopics': data})


@login_required
def syllabus_courses_json(request):
    """Return courses for a given syllabus as JSON (used by quiz bar)."""
    syllabus_id = request.GET.get('syllabus_id')
    if not syllabus_id:
        return JsonResponse({'courses': []})
    courses = Course.objects.filter(syllabus_id=syllabus_id).order_by('order', 'name')
    data = [{'id': c.id, 'name': c.name} for c in courses]
    return JsonResponse({'courses': data})


@login_required
def syllabuses_json(request):
    """Return all syllabuses as JSON."""
    syllabuses = Syllabus.objects.order_by('order', 'name')
    data = [{'id': s.id, 'name': s.name} for s in syllabuses]
    return JsonResponse({'syllabuses': data})
