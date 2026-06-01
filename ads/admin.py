from django.contrib import admin
from .models import PromoAd


@admin.register(PromoAd)
class PromoAdAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'is_active', 'show_to_members', 'created_at')
    list_editable = ('is_active',)
    list_filter = ('position', 'is_active', 'show_to_members')
    fields = ('title', 'position', 'html_content', 'image', 'link_url', 'is_active', 'show_to_members')
