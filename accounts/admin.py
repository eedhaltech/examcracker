from django.contrib import admin
from .models import UserProfile, DailyAttemptLog, UserTopicLevel


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_member', 'membership_expires', 'membership_active')
    list_filter = ('is_member',)
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('membership_active',)

    def membership_active(self, obj):
        return obj.membership_active
    membership_active.boolean = True


@admin.register(DailyAttemptLog)
class DailyAttemptLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'attempt_count')
    list_filter = ('date',)
    search_fields = ('user__email',)


@admin.register(UserTopicLevel)
class UserTopicLevelAdmin(admin.ModelAdmin):
    list_display = ('user', 'subtopic', 'current_level', 'total_attempted', 'total_correct', 'accuracy_display')
    list_filter = ('current_level',)
    search_fields = ('user__email',)

    def accuracy_display(self, obj):
        return f"{obj.accuracy:.1f}%"
    accuracy_display.short_description = 'Accuracy'
