from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator


class Syllabus(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'syllabuses'

    def __str__(self):
        return self.name


class Course(models.Model):
    syllabus = models.ForeignKey(
        Syllabus, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='courses'
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    icon = models.ImageField(upload_to='course_icons/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        if self.syllabus:
            return f"{self.name} ({self.syllabus.name})"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Topic(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=200)
    slug = models.SlugField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ('course', 'slug')

    def __str__(self):
        return f"{self.course.name} / {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class SubTopic(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics')
    name = models.CharField(max_length=200)
    slug = models.SlugField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ('topic', 'slug')

    def __str__(self):
        return f"{self.topic.name} / {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


DIFFICULTY_CHOICES = [('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')]
QUESTION_TYPE_CHOICES = [
    ('theory', 'Theory'),
    ('image', 'Image'),
    ('theory_image', 'Theory + Image'),
]


class Question(models.Model):
    subtopic = models.ForeignKey(SubTopic, on_delete=models.CASCADE, related_name='questions')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_questions',
        help_text='Who uploaded/created this question (used for admin-only automation)',
    )
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default='theory')
    body = models.TextField()
    image = models.ImageField(upload_to='question_images/', blank=True, null=True)
    explanation = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    level = models.PositiveIntegerField(default=1)  # 1–5
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    # Computed stats (updated async via Celery)
    total_attempted = models.PositiveIntegerField(default=0)
    total_correct = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['level', 'order', 'id']

    def __str__(self):
        return self.body[:80]

    @property
    def percent_correct(self):
        if self.total_attempted == 0:
            return 0
        return round((self.total_correct / self.total_attempted) * 100, 1)


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    label = models.CharField(max_length=1)  # A, B, C, D
    text = models.TextField()
    image = models.ImageField(upload_to='option_images/', blank=True, null=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['label']

    def __str__(self):
        return f"Q{self.question_id} — {self.label}: {self.text[:40]}"

# Import LevelConfig so it's part of this app's model registry
from .level_config import LevelConfig  # noqa: F401
