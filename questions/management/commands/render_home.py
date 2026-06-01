from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Render the questions/home.html template to stdout (development only).'

    def handle(self, *args, **options):
        from django.conf import settings
        if not settings.DEBUG:
            self.stderr.write('This command is for development only (DEBUG must be True).')
            return

        from django.template.loader import render_to_string
        from questions.models import Course, Syllabus

        syllabuses = list(
            Syllabus.objects.prefetch_related('courses__topics__subtopics').order_by('order', 'name')
        )
        courses = list(
            Course.objects.select_related('syllabus').prefetch_related('topics__subtopics').order_by('order', 'name')
        )

        html = render_to_string('questions/home.html', {
            'syllabuses': syllabuses,
            'courses': courses,
        })

        # Also write a static preview file so the dev server can serve it
        # without going through authentication middleware.
        import os
        from django.conf import settings
        out_path = os.path.join(settings.BASE_DIR, 'static', 'dev_preview_home.html')
        try:
            with open(out_path, 'w', encoding='utf-8') as fh:
                fh.write(html)
            self.stdout.write(f'Wrote preview to: {out_path}')
        except Exception as e:
            self.stderr.write(f'Failed to write preview file: {e}')

        self.stdout.write(html)
