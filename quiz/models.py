from django.db import models
from django.contrib.auth.models import User


class Attempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attempts')
    subtopic = models.ForeignKey('questions.SubTopic', on_delete=models.CASCADE, related_name='attempts')
    score = models.FloatField(default=0)
    negative_marking_enabled = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    is_complete = models.BooleanField(default=False)
    level_at_attempt = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.email} — {self.subtopic.name} — {self.started_at.date()}"

    @property
    def max_score(self):
        return self.answers.count()

    @property
    def correct_count(self):
        return self.answers.filter(is_correct=True).count()

    @property
    def incorrect_count(self):
        return self.answers.filter(is_correct=False, is_skipped=False, selected_option__isnull=False).count()

    @property
    def skipped_count(self):
        return self.answers.filter(is_skipped=True).count()


class Answer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey('questions.Question', on_delete=models.CASCADE, related_name='answers')
    selected_option = models.ForeignKey('questions.Option', on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    is_skipped = models.BooleanField(default=False)

    class Meta:
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f"Attempt {self.attempt_id} — Q{self.question_id}"
