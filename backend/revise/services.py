from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone

from .models import (
    Assessment,
    AssessmentProblem,
    ReviewEvent,
    UserProblem,
    UserProblemProgress,
    UserSettings,
)
from .sm2 import calculate_next_review


ASSESSMENT_TIME_LIMIT_MINUTES = 20
ASSESSMENT_MIN_PROBLEMS = 5
ASSESSMENT_MAX_PROBLEMS = 10


def _week_start(value):
    local_date = timezone.localtime(value).date()
    monday = local_date - timedelta(days=local_date.weekday())
    return timezone.make_aware(
        datetime.combine(monday, time.min),
        timezone.get_current_timezone(),
    )


@transaction.atomic
def generate_weekly_assessment(user):
    """Create one prioritized assessment per user per local calendar week."""
    week_start = _week_start(timezone.now())
    existing = Assessment.objects.filter(user=user, created_at__gte=week_start).first()
    if existing:
        return existing

    now = timezone.now()
    progress_items = list(
        UserProblemProgress.objects.filter(user=user, is_tracked=True)
        .select_related('problem__pattern')
        .order_by('next_review_date', '-confidence_rating')
    )
    if not progress_items:
        return None

    pattern_ids = {item.problem.pattern_id for item in progress_items if item.problem.pattern_id}
    review_averages = dict(
        ReviewEvent.objects.filter(user=user, problem__pattern_id__in=pattern_ids)
        .values_list('problem__pattern_id')
        .annotate(average=Avg('confidence'))
        .values_list('problem__pattern_id', 'average')
    )
    fallback_averages = {}
    for item in progress_items:
        pattern_id = item.problem.pattern_id
        if pattern_id and item.confidence_rating:
            fallback_averages.setdefault(pattern_id, []).append(item.confidence_rating)
    for pattern_id, ratings in fallback_averages.items():
        review_averages.setdefault(pattern_id, sum(ratings) / len(ratings))

    overdue_cutoff = now - timedelta(days=3)
    recent_cutoff = now - timedelta(days=7)

    def priority(item):
        next_review = item.next_review_date
        if next_review and next_review < overdue_cutoff:
            return (0, next_review.timestamp())
        if review_averages.get(item.problem.pattern_id, 5) < 3:
            return (1, -item.confidence_rating)
        if item.last_reviewed_at and item.last_reviewed_at >= recent_cutoff:
            return (2, -item.last_reviewed_at.timestamp())
        return (3, next_review.timestamp() if next_review else now.timestamp())

    selected = sorted(progress_items, key=priority)[:ASSESSMENT_MAX_PROBLEMS]
    if len(selected) < ASSESSMENT_MIN_PROBLEMS:
        # Include the user's most recently reviewed tracked items when the strict
        # due/weak/recent priorities do not provide five unique problems.
        selected_ids = {item.problem_id for item in selected}
        solved_items = UserProblem.objects.filter(user=user).exclude(
            problem_id__in=selected_ids,
        ).select_related('problem__pattern').order_by('-last_reviewed')
        for item in solved_items:
            selected.append(item)
            if len(selected) >= ASSESSMENT_MIN_PROBLEMS:
                break

    if not selected:
        return None

    assessment = Assessment.objects.create(
        user=user,
        time_limit_minutes=UserSettings.objects.filter(user=user).values_list(
            'assessment_time_limit',
            flat=True,
        ).first() or ASSESSMENT_TIME_LIMIT_MINUTES,
        total_problems=len(selected),
    )
    AssessmentProblem.objects.bulk_create([
        AssessmentProblem(assessment=assessment, problem=item.problem)
        for item in selected
    ])
    return assessment


def generate_assessments_for_active_users():
    user_model = get_user_model()
    generated = []
    for user in user_model.objects.filter(is_active=True).iterator():
        assessment = generate_weekly_assessment(user)
        if assessment:
            generated.append(assessment)
    return generated


@transaction.atomic
def complete_assessment(assessment):
    """Finalize unanswered items as missed and apply their results to SM-2."""
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    if assessment.status == 'completed':
        return assessment
    if assessment.status != 'in_progress':
        raise ValueError('Assessment must be started before it can be completed.')

    now = timezone.now()
    entries = list(
        assessment.problems.select_related('problem__pattern').order_by('id')
    )
    for entry in entries:
        if entry.status == 'unanswered':
            entry.status = 'missed'
            entry.answered_at = now
            entry.save(update_fields=['status', 'answered_at'])

        confidence = 4 if entry.status == 'solved' else 1
        progress, _ = UserProblemProgress.objects.get_or_create(
            user=assessment.user,
            problem=entry.problem,
            defaults={'is_tracked': True},
        )
        solved_progress, _ = UserProblem.objects.get_or_create(
            user=assessment.user,
            problem=entry.problem,
        )
        scheduled_for = (
            solved_progress.next_revision if solved_progress.revision_count else None
        )
        next_state = calculate_next_review(
            confidence=confidence,
            difficulty=entry.problem.difficulty,
            ef=progress.easiness_factor,
            interval=progress.interval,
            rep_number=progress.repetition_number,
        )
        progress.easiness_factor = next_state['easiness_factor']
        progress.interval = next_state['interval']
        progress.repetition_number = next_state['repetition_number']
        progress.confidence_rating = confidence
        progress.last_reviewed_at = now
        progress.next_review_date = now + timedelta(days=next_state['interval'])
        progress.is_tracked = True
        progress.updated_at = now
        progress.save()

        solved_progress.solved = True
        solved_progress.confidence = confidence
        solved_progress.interval = next_state['interval']
        solved_progress.last_reviewed = now
        solved_progress.next_revision = progress.next_review_date
        solved_progress.revision_count += 1
        solved_progress.save()
        ReviewEvent.objects.create(
            user=assessment.user,
            problem=entry.problem,
            confidence=confidence,
            scheduled_for=scheduled_for,
            reviewed_at=now,
        )

    solved_count = sum(entry.status == 'solved' for entry in entries)
    assessment.total_problems = len(entries)
    assessment.score_percentage = round(solved_count * 100 / len(entries)) if entries else 0
    assessment.completed_at = now
    assessment.status = 'completed'
    assessment.save(update_fields=[
        'total_problems',
        'score_percentage',
        'completed_at',
        'status',
    ])
    return assessment
