from django.contrib import admin
from .models import Attempt, Answer


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ('question', 'selected_option', 'is_correct', 'is_skipped')
    can_delete = False


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'subtopic', 'score', 'is_complete', 'level_at_attempt', 'started_at')
    list_filter = ('is_complete', 'level_at_attempt', 'negative_marking_enabled')
    search_fields = ('user__email',)
    readonly_fields = ('started_at', 'ended_at', 'time_taken_seconds', 'score')
    inlines = [AnswerInline]
