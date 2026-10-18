from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

class Solved(models.Model):
    q_id = models.IntegerField()
    q_name = models.CharField(default = str(q_id))
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
    leetcode_id = models.PositiveIntegerField(unique=True)
    link = models.URLField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    pattern = models.ForeignKey(Pattern, on_delete=models.PROTECT, related_name='problems')

    def __str__(self):
        return self.title


class UserProblem(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='problem_progress')
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='user_progress')
    solved = models.BooleanField(default=False)
    confidence = models.PositiveSmallIntegerField(null=True, blank=True)
    last_reviewed = models.DateTimeField(null=True, blank=True)
    next_revision = models.DateTimeField(null=True, blank=True)
    revision_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'problem'], name='unique_user_problem'),
        ]

    def __str__(self):
        return f'{self.user} - {self.problem}'


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
