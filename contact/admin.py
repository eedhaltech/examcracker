from django.contrib import admin
from django.utils.html import format_html
from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display  = ('name', 'rating_stars', 'body_preview', 'status', 'is_featured', 'created_at')
    list_editable = ('status', 'is_featured')
    list_filter   = ('status', 'is_featured', 'rating')
    search_fields = ('name', 'email', 'body')
    readonly_fields = ('user', 'name', 'email', 'created_at', 'updated_at')
    actions = ['approve_comments', 'reject_comments', 'feature_comments']

    def rating_stars(self, obj):
        return '★' * obj.rating + '☆' * (5 - obj.rating)
    rating_stars.short_description = 'Rating'

    def body_preview(self, obj):
        return obj.body[:80] + '…' if len(obj.body) > 80 else obj.body
    body_preview.short_description = 'Comment'

    def approve_comments(self, request, queryset):
        queryset.update(status='approved')
        self.message_user(request, f'{queryset.count()} comment(s) approved.')
    approve_comments.short_description = 'Approve selected comments'

    def reject_comments(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f'{queryset.count()} comment(s) rejected.')
    reject_comments.short_description = 'Reject selected comments'

    def feature_comments(self, request, queryset):
        queryset.update(is_featured=True, status='approved')
        self.message_user(request, f'{queryset.count()} comment(s) featured.')
    feature_comments.short_description = 'Feature selected comments'
