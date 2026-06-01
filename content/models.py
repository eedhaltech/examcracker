from django.db import models
from django.contrib.auth.models import User


class Comment(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending Review'),
        ('approved',  'Approved'),
        ('promoted',  'Promoted / Featured'),
        ('rejected',  'Rejected'),
    ]

    # Keep related_name unique (contact.Comment also uses related_name='comments')
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='content_comments')
    name        = models.CharField(max_length=100, blank=True, help_text='Auto-filled from account')
    body        = models.TextField(help_text='Share your experience with the quiz platform')
    rating      = models.PositiveSmallIntegerField(default=5, choices=[(i, f'{i} Star{"s" if i>1 else ""}') for i in range(1, 6)])
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_featured = models.BooleanField(default=False, help_text='Show on home page / contact page hero')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} — {self.rating}★ — {self.get_status_display()}"

    @property
    def display_name(self):
        return self.name or self.user.email.split('@')[0]

    @property
    def stars_range(self):
        return range(self.rating)

    @property
    def empty_stars_range(self):
        return range(5 - self.rating)


class SEOSettings(models.Model):
    """Singleton — one row for site-wide SEO defaults."""
    site_name        = models.CharField(max_length=100, default='MCQ Platform')
    home_title       = models.CharField(max_length=160, default='MCQ Platform — Practice Topic-wise Questions')
    home_description = models.TextField(default='Practice topic-wise MCQs with instant evaluation and performance tracking. Free and premium plans available.')
    home_keywords    = models.TextField(default='MCQ, multiple choice questions, exam preparation, quiz, practice test, aptitude, general knowledge')
    og_image         = models.ImageField(upload_to='seo/', blank=True, null=True, help_text='Default Open Graph image (1200×630px)')
    twitter_handle   = models.CharField(max_length=50, blank=True, help_text='@handle without @')
    google_analytics = models.CharField(max_length=50, blank=True, help_text='GA4 Measurement ID e.g. G-XXXXXXXXXX')
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'SEO Settings'
        verbose_name_plural = 'SEO Settings'

    def __str__(self):
        return 'SEO Settings'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
