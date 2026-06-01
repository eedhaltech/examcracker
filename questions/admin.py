import csv
import io
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.html import format_html
from django.http import HttpResponse
from .models import Course, Topic, SubTopic, Question, Option, Syllabus
from .level_config import LevelConfig
from .import_logic import import_questions_from_csv


class OptionInline(admin.TabularInline):
    model = Option
    extra = 4
    max_num = 4
    fields = ('label', 'text', 'image', 'is_correct')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    inlines = [OptionInline]
    list_display = ('id', 'body_preview', 'subtopic', 'question_type', 'difficulty', 'level', 'percent_correct_display', 'total_attempted')
    list_filter = ('subtopic__topic__course', 'subtopic__topic', 'subtopic', 'difficulty', 'level', 'question_type')
    search_fields = ('body',)
    readonly_fields = ('total_attempted', 'total_correct', 'percent_correct_display', 'created_at')
    fields = ('subtopic', 'created_by', 'question_type', 'body', 'image', 'explanation', 'difficulty', 'level', 'order', 'created_at', 'total_attempted', 'total_correct', 'percent_correct_display')

    def save_model(self, request, obj, form, change):
        # Mark questions created/edited from admin as "admin uploaded" for automation.
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def body_preview(self, obj):
        return obj.body[:80] + '...' if len(obj.body) > 80 else obj.body
    body_preview.short_description = 'Question'

    def percent_correct_display(self, obj):
        return f"{obj.percent_correct}%"
    percent_correct_display.short_description = '% Correct'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('upload-csv/', self.admin_site.admin_view(self.upload_csv_view), name='questions_question_upload_csv'),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['upload_csv_url'] = 'upload-csv/'
        return super().changelist_view(request, extra_context=extra_context)

    def upload_csv_view(self, request):
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                messages.error(request, 'No file uploaded.')
                return redirect('.')
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'File must be a .csv')
                return redirect('.')
            try:
                decoded = csv_file.read().decode('utf-8')
                result = import_questions_from_csv(io.StringIO(decoded), created_by=request.user)
                messages.success(
                    request,
                    f"Import complete: {result['inserted']} inserted, "
                    f"{result['skipped']} skipped, {result['errors']} errors."
                )
                if result['error_details']:
                    for detail in result['error_details']:
                        messages.warning(request, detail)
            except Exception as e:
                messages.error(request, f"Import failed: {e}")
            return redirect('../')

        sample_csv_url = '/static/sample_questions.csv'
        context = {
            **self.admin_site.each_context(request),
            'title': 'Upload Questions CSV',
            'sample_csv_url': sample_csv_url,
        }
        return render(request, 'admin/questions/upload_csv.html', context)


@admin.register(LevelConfig)
class LevelConfigAdmin(admin.ModelAdmin):
    # NOTE: list_editable fields must appear in list_display.
    # 'level' is the link column (first), editable fields follow immediately.
    list_display = ('level', 'requires_membership', 'label', 'description', 'access_badge', 'question_count')
    list_editable = ('requires_membership', 'label', 'description')
    ordering = ['level']
    fields = ('level', 'requires_membership', 'label', 'description')

    def access_badge(self, obj):
        if obj.requires_membership:
            return format_html(
                '<span style="background:#EF9F27;color:#fff;padding:3px 10px;'
                'border-radius:12px;font-size:12px;font-weight:600;">🔒 Members Only</span>'
            )
        return format_html(
            '<span style="background:#10b981;color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:12px;font-weight:600;">🆓 Free</span>'
        )
    access_badge.short_description = 'Status'

    def question_count(self, obj):
        count = Question.objects.filter(level=obj.level).count()
        return format_html('<strong>{}</strong> questions', count)
    question_count.short_description = 'Questions'

    def has_add_permission(self, request):
        return LevelConfig.objects.count() < 5

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'Level Access Configuration'
        # Auto-create all 5 levels on first visit so admin sees them immediately
        existing = set(LevelConfig.objects.values_list('level', flat=True))
        defaults = {1: False, 2: False, 3: True, 4: True, 5: True}
        labels = {1: 'Beginner', 2: 'Elementary', 3: 'Intermediate', 4: 'Advanced', 5: 'Expert'}
        descriptions = {
            1: 'Basic questions — free for everyone',
            2: 'Easy questions — free for everyone',
            3: 'Medium questions — members only',
            4: 'Hard questions — members only',
            5: 'Expert questions — members only',
        }
        for lvl, paid in defaults.items():
            if lvl not in existing:
                LevelConfig.objects.create(
                    level=lvl,
                    requires_membership=paid,
                    label=labels[lvl],
                    description=descriptions[lvl],
                )
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Syllabus)
class SyllabusAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'order', 'created_at', 'course_count')
    ordering = ['order', 'name']
    fields = ('name', 'description', 'order')

    def course_count(self, obj):
        return obj.courses.count()
    course_count.short_description = 'Courses'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'syllabus', 'slug', 'order')
    list_filter = ('syllabus',)
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'slug', 'order')
    list_filter = ('course',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(SubTopic)
class SubTopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'topic', 'slug', 'order')
    list_filter = ('topic__course', 'topic')
    prepopulated_fields = {'slug': ('name',)}
