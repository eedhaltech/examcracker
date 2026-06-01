from django.db import models

PRODUCT_TYPE_CHOICES = [
    ('book', 'Book'),
    ('affiliate', 'Affiliate Link'),
    ('course', 'Online Course'),
    ('tool', 'Tool / Resource'),
]


class Product(models.Model):
    title = models.CharField(max_length=200)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES, default='book')
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    affiliate_url = models.URLField(blank=True, help_text='Buy / affiliate link (optional if you provide a downloadable file)')
    download_file = models.FileField(upload_to='products/files/', blank=True, null=True, help_text='Optional downloadable file (PDF/ZIP/etc.)')
    price_display = models.CharField(max_length=50, blank=True, help_text='e.g. ₹299 or Free')
    badge = models.CharField(max_length=50, blank=True, help_text='e.g. Bestseller, Recommended')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_product_type_display()})"
