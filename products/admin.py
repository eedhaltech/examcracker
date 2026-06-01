from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'product_type', 'price_display', 'is_active', 'order', 'created_at')
    list_editable = ('is_active', 'order')
    list_filter = ('product_type', 'is_active')
    search_fields = ('title', 'description')
    fields = ('title', 'product_type', 'description', 'image', 'affiliate_url',
              'download_file', 'price_display', 'badge', 'is_active', 'order')
