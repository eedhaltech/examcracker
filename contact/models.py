from django.db import models
from django.contrib.auth.models import User


class Comment(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    name        = models.CharField(max_length=100)          # auto-filled from user
    email       = models.EmailField()                        # auto-filled from user
    body        = models.TextField(max_length=1000)
    rating      = models.PositiveSmallIntegerField(
                    default=5,
                    choices=[(i, f'{i} Star{"s" if i>1 else ""}') for i in range(1, 6)]
                  )
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    is_featured = models.BooleanField(default=False, help_text='Show on homepage / top of list')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', '-created_at']

    def __str__(self):
        return f"{self.name} — {self.rating}★ ({self.status})"

    @property
    def stars_range(self):
        return range(self.rating)

    @property
    def empty_stars_range(self):
        return range(5 - self.rating)
