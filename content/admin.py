from django.contrib import admin

from .models import Comment, SEOSettings


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("user", "rating", "status", "is_featured", "created_at")
    list_filter = ("status", "is_featured", "rating")
    search_fields = ("user__email", "name", "body")
    list_editable = ("status", "is_featured")


@admin.register(SEOSettings)
class SEOSettingsAdmin(admin.ModelAdmin):
    """
    Singleton model (one row). Edit this to update site-wide SEO defaults.
    """
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
