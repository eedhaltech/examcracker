from django.db import models

AD_POSITION_CHOICES = [
    ('display_sidebar', 'Display Ad — Right Sidebar'),
    ('closing', 'Closing Ad — Between Questions'),
    ('overlapping', 'Overlapping Closing Ad — Interstitial'),
]


class PromoAd(models.Model):
    title = models.CharField(max_length=200)
    position = models.CharField(max_length=30, choices=AD_POSITION_CHOICES)
    html_content = models.TextField(blank=True, help_text='Custom HTML/CSS for the promo ad')
    image = models.ImageField(upload_to='promo_ads/', blank=True, null=True)
    link_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    show_to_members = models.BooleanField(default=False, help_text='If False, shown to non-members only')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_position_display()})"
