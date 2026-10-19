from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify


class Solved(models.Model):
    q_id = models.IntegerField()
    q_name = models.CharField(default=str(q_id))
    q_link = models.TextField()

    def __str__(self):
        return self.q_name


class Pattern(models.Model):
    p_name = models.CharField(max_length=100)

    def __str__(self):
        return self.p_name


class Problem(models.Model):
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    leetcode_id = models.PositiveIntegerField(unique=True)
    link = models.URLField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    pattern = models.ForeignKey(Pattern, on_delete=models.PROTECT, related_name='problems', null=True, blank=True)
    patterns = models.ManyToManyField(Pattern, related_name='problem_memberships', blank=True)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            if not base_slug:
                base_slug = f'problem-{self.leetcode_id}'
            unique_slug = base_slug
            counter = 1
            while Problem.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class GlobalProblem(Problem):
    class Meta:
        proxy = True
        verbose_name = 'global problem'
        verbose_name_plural = 'global problems'


class UserProblem(models.Model):
    SOURCE_CHOICES = [
        ('manual', 'manual'),
        ('import', 'import'),
    ]

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='problem_progress')
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='user_progress')
    solved = models.BooleanField(default=False)
    confidence = models.PositiveSmallIntegerField(null=True, blank=True)
    interval = models.PositiveIntegerField(default=0)
    last_reviewed = models.DateTimeField(null=True, blank=True)
    next_revision = models.DateTimeField(null=True, blank=True)
    revision_count = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'problem'], name='unique_user_problem'),
        ]

    def __str__(self):
        return f'{self.user} - {self.problem}'


class UserProblemProgress(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='sm2_progress')
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='sm2_progress')
    is_tracked = models.BooleanField(default=True)
    easiness_factor = models.FloatField(default=2.5)
    interval = models.PositiveIntegerField(default=0)
    repetition_number = models.PositiveIntegerField(default=0)
    next_review_date = models.DateTimeField(null=True, blank=True)
    confidence_rating = models.PositiveSmallIntegerField(default=0)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'problem'], name='unique_sm2_user_problem'),
        ]
        ordering = ['next_review_date', '-confidence_rating']

    def __str__(self):
        return f'{self.user} - {self.problem} ({self.confidence_rating}/5)'


class DSASheet(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class DSASheetProblem(models.Model):
    sheet = models.ForeignKey(DSASheet, on_delete=models.CASCADE, related_name='problems')
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='sheets')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sheet', 'problem'], name='unique_sheet_problem'),
        ]

    def __str__(self):
        return f'{self.sheet} - {self.problem}'


class ReviewEvent(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='review_events')
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='review_events')
    confidence = models.PositiveSmallIntegerField()
    scheduled_for = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['reviewed_at']
        indexes = [
            models.Index(fields=['user', 'reviewed_at'], name='review_user_reviewed_idx'),
            models.Index(fields=['user', 'scheduled_for'], name='review_user_due_idx'),
        ]

    def __str__(self):
        return f'{self.user} - {self.problem} ({self.confidence}/5)'
