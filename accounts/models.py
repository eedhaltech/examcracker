from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_member = models.BooleanField(default=False)
    membership_expires = models.DateField(null=True, blank=True)
    google_id = models.CharField(max_length=200, blank=True)
    avatar_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.user.email} — {'Member' if self.membership_active else 'Free'}"

    @property
    def membership_active(self):
        if not self.is_member:
            return False
        return self.membership_expires and self.membership_expires >= timezone.now().date()


class DailyAttemptLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_logs')
    date = models.DateField()
    attempt_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date')

    def __str__(self):
        return f"{self.user.email} — {self.date} — {self.attempt_count} attempts"


class UserTopicLevel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='topic_levels')
    subtopic = models.ForeignKey('questions.SubTopic', on_delete=models.CASCADE, related_name='user_levels')
    current_level = models.PositiveIntegerField(default=1)  # 1–5
    total_attempted = models.PositiveIntegerField(default=0)
    total_correct = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'subtopic')

    def __str__(self):
        return f"{self.user.email} — {self.subtopic.name} — Level {self.current_level}"

    @property
    def accuracy(self):
        if self.total_attempted == 0:
            return 0
        return (self.total_correct / self.total_attempted) * 100
