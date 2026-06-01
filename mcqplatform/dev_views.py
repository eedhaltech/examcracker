from django.conf import settings
from django.http import Http404
from django.shortcuts import render


def preview_home(request):
    """Render the homepage template without requiring authentication.

    This view is intentionally only enabled when settings.DEBUG is True and
    should never be exposed in production.
    """
    if not settings.DEBUG:
        raise Http404()

    # Import models lazily to avoid import cycles when not used.
    from questions.models import Course, Syllabus

    syllabuses = list(
        Syllabus.objects.prefetch_related('courses__topics__subtopics').order_by('order', 'name')
    )
    courses = list(
        Course.objects.select_related('syllabus').prefetch_related('topics__subtopics').order_by('order', 'name')
    )

    return render(request, 'questions/home.html', {
        'syllabuses': syllabuses,
        'courses': courses,
    })
