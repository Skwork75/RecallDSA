from django.db import models
from django.contrib.auth import get_user_model

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
