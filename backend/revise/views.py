from datetime import datetime, time, timedelta
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Avg, Count, Exists, F, Min, OuterRef, Q, Window
from django.db.models.functions import TruncDate
from django.db.models.functions.window import RowNumber
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import (
    AssessmentSerializer,
    AssessmentProblemSerializer,
    ActivityHeatmapDaySerializer,
    ConfidenceTrendDaySerializer,
    ProblemSerializer,
    PatternStrengthResponseSerializer,
    RecommendationSerializer,
    RegisterSerializer,
    UserProblemSerializer,
    UserSerializer,
    DSASheetSerializer,
    DSASheetProblemSerializer,
)
from .models import (
    Assessment,
    AssessmentProblem,
    Problem,
    ReviewEvent,
    UserProblem,
    DSASheet,
    DSASheetProblem,
    Pattern,
    UserProblemProgress,
)
from .sm2 import calculate_next_review
from .services import complete_assessment, generate_weekly_assessment
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status


def next_revision_for(confidence, difficulty, revision_count=0):
    difficulty_bonus = {
        'Easy': 1.0,
        'Medium': 1.35,
        'Hard': 1.7,
    }.get(difficulty, 1.0)

    interval_map = {
        1: 1,
        2: 2,
        3: 4,
        4: 9,
        5: 16,
    }

    base_days = interval_map.get(confidence, 3)
    spaced_days = max(base_days, 3 + revision_count)
    return timezone.now() + timedelta(days=round(spaced_days * difficulty_bonus))

@api_view(["GET", "POST"])
def home(request):
    if request.method == 'POST':
        title = request.data.get('title')
        leetcode_id = request.data.get('leetcode_id')
        link = request.data.get('link')
        difficulty = request.data.get('difficulty')
        if not title or not leetcode_id or not link or not difficulty:
            return Response({'detail': 'title, leetcode_id, link, and difficulty are required.'}, status=status.HTTP_400_BAD_REQUEST)

        pattern_name = request.data.get('pattern') or request.data.get('p_name')
        pattern = None
        if pattern_name:
            pattern, _ = Pattern.objects.get_or_create(p_name=pattern_name)

        problem, created = Problem.objects.get_or_create(
            leetcode_id=leetcode_id,
            defaults={
                'title': title,
                'link': link,
                'difficulty': difficulty,
                'pattern': pattern,
                'description': request.data.get('description', ''),
            },
        )
        if pattern and problem.pattern is None:
            problem.pattern = pattern
            problem.save(update_fields=['pattern'])
        return Response(ProblemSerializer(problem).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    questions = Problem.objects.select_related('pattern').prefetch_related('patterns').all()
    serializer = ProblemSerializer(questions, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tracked_problems(request):
    progress_items = UserProblemProgress.objects.filter(
        user=request.user,
        is_tracked=True,
    ).select_related('problem__pattern').prefetch_related('problem__patterns')

    return Response([
        {
            'id': progress.id,
            'problem': ProblemSerializer(progress.problem).data,
            'confidence_rating': progress.confidence_rating,
            'interval': progress.interval,
            'next_review_date': progress.next_review_date,
            'last_reviewed_at': progress.last_reviewed_at,
        }
        for progress in progress_items
    ])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dsasheets(request):
    sheets = DSASheet.objects.annotate(
        sheet_problem_count=Count('problems', distinct=True),
        sheet_tracked_count=Count(
            'problems',
            filter=Q(
                problems__problem__sm2_progress__user=request.user,
                problems__problem__sm2_progress__is_tracked=True,
            ),
            distinct=True,
        ),
    ).filter(problems__isnull=False).distinct()
    if request.query_params.get('featured', '').lower() in ('1', 'true'):
        sheets = sheets.filter(is_featured=True)
    return Response(DSASheetSerializer(sheets, many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dsasheet_detail(request, slug):
    try:
        sheet = DSASheet.objects.annotate(
            sheet_problem_count=Count('problems', distinct=True),
            sheet_tracked_count=Count(
                'problems',
                filter=Q(
                    problems__problem__sm2_progress__user=request.user,
                    problems__problem__sm2_progress__is_tracked=True,
                ),
                distinct=True,
            ),
        ).filter(problems__isnull=False).distinct().get(slug=slug)
    except DSASheet.DoesNotExist:
        return Response({'detail': 'Sheet not found.'}, status=status.HTTP_404_NOT_FOUND)

    is_tracked_by_user = UserProblemProgress.objects.filter(
        user=request.user,
        problem_id=OuterRef('problem_id'),
        is_tracked=True,
    )
    serialized_problems = DSASheetProblemSerializer(
        sheet.problems.select_related('problem__pattern').prefetch_related(
            'problem__patterns',
        ).annotate(is_tracked_by_user=Exists(is_tracked_by_user)),
        many=True,
        context={'request': request},
    ).data
    grouped = {}
    for item in serialized_problems:
        pattern = item['problem'].get('pattern') or {}
        category = item['category'] or pattern.get('p_name') or 'Uncategorized'
        grouped.setdefault(category, []).append(item)

    return Response({
        **DSASheetSerializer(sheet, context={'request': request}).data,
        'categories': [
            {'name': category, 'problems': problems}
            for category, problems in grouped.items()
        ],
    })


def _track_sheet_problems(user, problems):
    added = 0
    for problem in problems:
        _, was_created = UserProblemProgress.objects.get_or_create(
            user=user,
            problem=problem,
            defaults={
                'is_tracked': True,
                'easiness_factor': 2.5,
                'interval': 0,
                'repetition_number': 0,
            },
        )
        if was_created:
            added += 1
        else:
            added += UserProblemProgress.objects.filter(user=user, problem=problem, is_tracked=False).update(
                is_tracked=True,
                updated_at=timezone.now(),
            )
    return added


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def track_all_sheet_problems(request, slug):
    try:
        sheet = DSASheet.objects.get(slug=slug)
    except DSASheet.DoesNotExist:
        return Response({'detail': 'Sheet not found.'}, status=status.HTTP_404_NOT_FOUND)

    problems = Problem.objects.filter(sheets__sheet=sheet).distinct()
    added_count = _track_sheet_problems(request.user, problems)
    return Response({
        'added_count': added_count,
        'already_tracked_count': problems.count() - added_count,
        'total_count': problems.count(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def track_selected_sheet_problems(request, slug):
    try:
        sheet = DSASheet.objects.get(slug=slug)
    except DSASheet.DoesNotExist:
        return Response({'detail': 'Sheet not found.'}, status=status.HTTP_404_NOT_FOUND)

    problem_ids = request.data.get('problem_ids')
    if not isinstance(problem_ids, list) or not problem_ids:
        return Response({'detail': 'problem_ids must be a non-empty list.'}, status=status.HTTP_400_BAD_REQUEST)
    if any(not isinstance(problem_id, int) or isinstance(problem_id, bool) for problem_id in problem_ids):
        return Response({'detail': 'problem_ids must contain integer IDs.'}, status=status.HTTP_400_BAD_REQUEST)

    problems = Problem.objects.filter(sheets__sheet=sheet, id__in=set(problem_ids)).distinct()
    if problems.count() != len(set(problem_ids)):
        return Response({'detail': 'One or more problems are not part of this sheet.'}, status=status.HTTP_400_BAD_REQUEST)

    added_count = _track_sheet_problems(request.user, problems)
    return Response({
        'added_count': added_count,
        'already_tracked_count': problems.count() - added_count,
        'total_count': problems.count(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_dsasheet(request):
    name = request.data.get('name')
    if not name:
        return Response({'detail': 'A sheet name is required.'}, status=status.HTTP_400_BAD_REQUEST)

    sheet = DSASheet.objects.create(title=name, description=request.data.get('description', ''))
    return Response(DSASheetSerializer(sheet).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_problem_to_sheet(request, sheet_id):
    try:
        sheet = DSASheet.objects.get(id=sheet_id)
    except DSASheet.DoesNotExist:
        return Response({'detail': 'Sheet not found.'}, status=status.HTTP_404_NOT_FOUND)

    problem_id = request.data.get('problem_id')
    if not problem_id:
        return Response({'detail': 'A problem_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        problem = Problem.objects.get(id=problem_id)
    except Problem.DoesNotExist:
        return Response({'detail': 'Problem not found.'}, status=status.HTTP_404_NOT_FOUND)

    item, created = DSASheetProblem.objects.get_or_create(sheet=sheet, problem=problem)
    if created:
        sheet.total_problems = sheet.problems.count()
        sheet.save(update_fields=['total_problems'])
    return Response({
        'created': created,
        'sheet_id': sheet.id,
        'problem_id': problem.id,
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    refresh = RefreshToken.for_user(user)
    return Response({
        'user': UserSerializer(user).data,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response(
            {'detail': 'Invalid username or password.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    refresh = RefreshToken.for_user(user)
    return Response({
        'user': UserSerializer(user).data,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    return Response(UserSerializer(request.user).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    solved_problems = UserProblem.objects.filter(
        user=request.user,
        solved=True,
    ).select_related('problem__pattern').order_by('-last_reviewed')
    return Response({
        'user': UserSerializer(request.user).data,
        'solved_problems': UserProblemSerializer(solved_problems, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def submit_review(request):
    """Submit an SM-2 review and update the user's per-problem progress."""
    problem_id = request.data.get('problem_id')
    confidence = request.data.get('confidence_rating')
    if confidence is None:
        confidence = request.data.get('confidence')

    if problem_id is None or confidence is None:
        return Response({'detail': 'problem_id and confidence_rating are required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        confidence = int(confidence)
    except (TypeError, ValueError):
        return Response({'detail': 'confidence_rating must be an integer between 1 and 5.'}, status=status.HTTP_400_BAD_REQUEST)

    if confidence < 1 or confidence > 5:
        return Response({'detail': 'confidence_rating must be between 1 and 5.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        problem = Problem.objects.select_related('pattern').get(id=problem_id)
    except Problem.DoesNotExist:
        return Response({'detail': 'Problem not found.'}, status=status.HTTP_404_NOT_FOUND)

    progress, _ = UserProblemProgress.objects.get_or_create(
        user=request.user,
        problem=problem,
        defaults={'is_tracked': True, 'easiness_factor': 2.5, 'interval': 0, 'repetition_number': 0},
    )

    current_interval = progress.interval or 0
    current_rep_number = progress.repetition_number or 0
    current_ef = progress.easiness_factor or 2.5
    next_state = calculate_next_review(
        confidence=confidence,
        difficulty=problem.difficulty,
        ef=current_ef,
        interval=current_interval,
        rep_number=current_rep_number,
    )

    progress.easiness_factor = next_state['easiness_factor']
    progress.interval = next_state['interval']
    progress.repetition_number = next_state['repetition_number']
    progress.confidence_rating = confidence
    progress.last_reviewed_at = timezone.now()
    progress.next_review_date = timezone.now() + timedelta(days=next_state['interval'])
    progress.is_tracked = True
    progress.updated_at = timezone.now()
    progress.save()

    solved_progress, _ = UserProblem.objects.get_or_create(
        user=request.user,
        problem=problem,
    )
    scheduled_for = solved_progress.next_revision if solved_progress.revision_count else None
    solved_progress.solved = True
    solved_progress.confidence = confidence
    solved_progress.interval = next_state['interval']
    solved_progress.last_reviewed = progress.last_reviewed_at
    solved_progress.next_revision = progress.next_review_date
    solved_progress.revision_count += 1
    solved_progress.save()
    ReviewEvent.objects.create(
        user=request.user,
        problem=problem,
        confidence=confidence,
        scheduled_for=scheduled_for,
        reviewed_at=progress.last_reviewed_at,
    )

    return Response({
        'problem_id': problem.id,
        'confidence_rating': confidence,
        'next_review_date': progress.next_review_date,
        'interval': progress.interval,
        'repetition_number': progress.repetition_number,
        'easiness_factor': progress.easiness_factor,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def due_today(request):
    today = timezone.now().date()
    items = UserProblemProgress.objects.filter(
        user=request.user,
        is_tracked=True,
        next_review_date__date__lte=today,
    ).select_related('problem__pattern').order_by('next_review_date')

    payload = []
    for item in items:
        overdue_days = max(0, (today - item.next_review_date.date()).days) if item.next_review_date else 0
        payload.append({
            'id': item.id,
            'problem': ProblemSerializer(item.problem).data,
            'confidence_rating': item.confidence_rating,
            'interval': item.interval,
            'repetition_number': item.repetition_number,
            'easiness_factor': item.easiness_factor,
            'next_review_date': item.next_review_date,
            'overdue_days': overdue_days,
        })

    payload.sort(key=lambda item: (-int(item['overdue_days']), item['next_review_date'] or timezone.now()))
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def today_revisions(request):
    now = timezone.now()
    due_items = UserProblem.objects.filter(
        user=request.user,
        solved=True,
        next_revision__lte=now,
    ).select_related('problem__pattern').order_by('next_revision')
    return Response(UserProblemSerializer(due_items, many=True).data)


def _review_streaks(review_dates, today):
    ordered_dates = sorted(set(review_dates))
    if not ordered_dates:
        return 0, 0

    longest = current_run = 1
    for previous, current in zip(ordered_dates, ordered_dates[1:]):
        if (current - previous).days <= 2:
            current_run += 1
        else:
            current_run = 1
        longest = max(longest, current_run)

    current_streak = 0
    if (today - ordered_dates[-1]).days <= 2:
        current_streak = 1
        for previous, current in zip(reversed(ordered_dates[:-1]), reversed(ordered_dates[1:])):
            if (current - previous).days > 2:
                break
            current_streak += 1

    return current_streak, longest


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    user = request.user
    now = timezone.now()
    today = timezone.localdate(now)
    week_start_date = today - timedelta(days=today.weekday())
    week_end_date = week_start_date + timedelta(days=7)
    review_window_start = timezone.make_aware(
        datetime.combine(today - timedelta(days=6), time.min),
        timezone.get_current_timezone(),
    )
    review_window_end = timezone.make_aware(
        datetime.combine(today + timedelta(days=1), time.min),
        timezone.get_current_timezone(),
    )
    week_start = timezone.make_aware(
        datetime.combine(week_start_date, time.min),
        timezone.get_current_timezone(),
    )
    week_end = timezone.make_aware(
        datetime.combine(week_end_date, time.min),
        timezone.get_current_timezone(),
    )

    tracked = UserProblemProgress.objects.filter(user=user, is_tracked=True)
    tracked_metrics = tracked.aggregate(
        total=Count('id'),
        due_today=Count('id', filter=Q(next_review_date__date__lte=today)),
        due_this_week=Count('id', filter=Q(next_review_date__date__lt=week_end_date)),
        patterns=Count(
            'problem__pattern_id',
            filter=Q(problem__pattern_id__isnull=False),
            distinct=True,
        ),
        next_review=Min('next_review_date', filter=Q(next_review_date__gt=now)),
    )
    review_events = ReviewEvent.objects.filter(user=user)
    review_metrics = review_events.aggregate(
        total=Count('id'),
        average=Avg('confidence'),
        recent=Count('id', filter=Q(
            reviewed_at__gte=review_window_start,
            reviewed_at__lt=review_window_end,
        )),
        this_week=Count('id', filter=Q(
            reviewed_at__gte=week_start,
            reviewed_at__lt=now,
        )),
    )
    reviews_done = review_metrics['total']
    recent_reviews_done = review_metrics['recent']
    outstanding_reviews = tracked.filter(
        next_review_date__gte=review_window_start,
        next_review_date__lt=review_window_end,
    ).count()
    reviews_due = recent_reviews_done + outstanding_reviews

    activity_start_date = today - timedelta(days=89)
    activity_start = timezone.make_aware(
        datetime.combine(activity_start_date, time.min),
        timezone.get_current_timezone(),
    )
    activity = {
        row['review_day']: row['count']
        for row in review_events.filter(
            reviewed_at__gte=activity_start,
            reviewed_at__lt=review_window_end,
        ).annotate(
            review_day=TruncDate('reviewed_at'),
        ).values('review_day').annotate(
            count=Count('id'),
        )
    }
    activity_last_90days = [
        {
            'date': activity_start_date + timedelta(days=offset),
            'count': activity.get(activity_start_date + timedelta(days=offset), 0),
        }
        for offset in range(90)
    ]
    review_dates = review_events.annotate(
        review_day=TruncDate('reviewed_at'),
    ).values_list('review_day', flat=True).distinct()
    current_streak, longest_streak = _review_streaks(review_dates, today)

    tracked_count = tracked_metrics['total']
    sheets_in_progress = DSASheet.objects.annotate(
        sheet_problem_count=Count('problems', distinct=True),
        sheet_tracked_count=Count(
            'problems',
            filter=Q(
                problems__problem__sm2_progress__user=user,
                problems__problem__sm2_progress__is_tracked=True,
            ),
            distinct=True,
        ),
    ).filter(
        sheet_tracked_count__gt=0,
    ).exclude(
        sheet_tracked_count=F('sheet_problem_count'),
    ).count()
    this_week_solved = UserProblem.objects.filter(
        user=user,
        solved=True,
        created_at__gte=week_start,
        created_at__lt=week_end,
    ).count()

    return Response({
        'total_problems_tracked': tracked_count,
        'problems_due_today': tracked_metrics['due_today'],
        'problems_due_this_week': tracked_metrics['due_this_week'],
        'current_streak': current_streak,
        'longest_streak': longest_streak,
        'revision_completion_7days': round(recent_reviews_done * 100 / reviews_due) if reviews_due else 0,
        'total_reviews_done': reviews_done,
        'avg_confidence': round(review_metrics['average'], 2) if review_metrics['average'] is not None else None,
        'patterns_covered': tracked_metrics['patterns'],
        'sheets_in_progress': sheets_in_progress,
        'this_week_solved': this_week_solved,
        'this_week_reviewed': review_metrics['this_week'],
        'activity_last_90days': activity_last_90days,
        'has_leetcode_connected': UserProblem.objects.filter(user=user, source='import').exists(),
        'onboarding_status': 'new' if tracked_count == 0 else 'active' if reviews_done else 'exploring',
        'next_review_date': tracked_metrics['next_review'],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def weekly_assessment(request):
    now = timezone.now()
    problems = UserProblem.objects.filter(
        user=request.user,
        solved=True,
    ).select_related('problem__pattern').order_by('next_revision', 'confidence')

    due_or_weak = [
        item for item in problems
        if item.next_revision is None
        or item.next_revision <= now
        or (item.confidence is not None and item.confidence <= 2)
    ]

    if not due_or_weak:
        due_or_weak = list(problems[:5])

    selected = sorted(
        due_or_weak,
        key=lambda item: (
            0 if item.next_revision is not None and item.next_revision <= now else 1,
            item.confidence if item.confidence is not None else 5,
            item.next_revision or now,
        ),
    )[:5]

    return Response(UserProblemSerializer(selected, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_assessment(request):
    now = timezone.now()
    week_start = now - timedelta(days=now.weekday())
    week_start = timezone.make_aware(
        datetime.combine(
            timezone.localtime(week_start).date(),
            time.min,
        ),
        timezone.get_current_timezone(),
    )
    assessment = Assessment.objects.filter(
        user=request.user,
        created_at__gte=week_start,
    ).prefetch_related('problems__problem__pattern', 'problems__problem__patterns').first()
    if assessment is None:
        assessment = generate_weekly_assessment(request.user)
    if assessment is None:
        return Response(None)
    return Response(AssessmentSerializer(assessment).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def assessment_history(request):
    assessments = Assessment.objects.filter(user=request.user).prefetch_related(
        'problems__problem__pattern',
        'problems__problem__patterns',
    )
    return Response(AssessmentSerializer(assessments, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def start_assessment(request, assessment_id):
    try:
        assessment = Assessment.objects.select_for_update().get(pk=assessment_id, user=request.user)
    except Assessment.DoesNotExist:
        return Response({'detail': 'Assessment not found.'}, status=status.HTTP_404_NOT_FOUND)
    if assessment.status == 'scheduled':
        assessment.status = 'in_progress'
        assessment.started_at = timezone.now()
        assessment.save(update_fields=['status', 'started_at'])
    elif assessment.status != 'in_progress':
        return Response({'detail': 'This assessment has already been completed.'}, status=status.HTTP_409_CONFLICT)
    assessment = Assessment.objects.prefetch_related(
        'problems__problem__pattern',
        'problems__problem__patterns',
    ).get(pk=assessment.pk)
    return Response(AssessmentSerializer(assessment).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def submit_assessment_answer(request, assessment_id):
    try:
        assessment = Assessment.objects.select_for_update().get(pk=assessment_id, user=request.user)
    except Assessment.DoesNotExist:
        return Response({'detail': 'Assessment not found.'}, status=status.HTTP_404_NOT_FOUND)
    if assessment.status != 'in_progress':
        return Response({'detail': 'Assessment is not in progress.'}, status=status.HTTP_409_CONFLICT)

    problem_id = request.data.get('problem_id')
    answer = request.data.get('status')
    if answer not in ('solved', 'missed'):
        return Response({'detail': 'status must be either solved or missed.'}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(problem_id, int) or isinstance(problem_id, bool):
        return Response({'detail': 'problem_id must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        entry = AssessmentProblem.objects.get(assessment=assessment, problem_id=problem_id)
    except AssessmentProblem.DoesNotExist:
        return Response({'detail': 'Problem is not part of this assessment.'}, status=status.HTTP_400_BAD_REQUEST)
    entry.status = answer
    entry.answered_at = timezone.now()
    entry.save(update_fields=['status', 'answered_at'])
    return Response(AssessmentProblemSerializer(entry).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def finish_assessment(request, assessment_id):
    try:
        assessment = Assessment.objects.get(pk=assessment_id, user=request.user)
    except Assessment.DoesNotExist:
        return Response({'detail': 'Assessment not found.'}, status=status.HTTP_404_NOT_FOUND)
    try:
        assessment = complete_assessment(assessment)
    except ValueError as error:
        return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)
    assessment = Assessment.objects.prefetch_related(
        'problems__problem__pattern',
        'problems__problem__patterns',
    ).get(pk=assessment.pk)
    return Response(AssessmentSerializer(assessment).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    user = request.user
    now = timezone.now()
    week_start = now - timedelta(days=7)
    progress_items = UserProblem.objects.filter(
        user=user,
        solved=True,
    ).select_related('problem__pattern')
    events = ReviewEvent.objects.filter(user=user).select_related('problem__pattern')

    pattern_totals = {}
    event_problem_ids = set()
    review_dates = set()
    for event in events:
        pattern = event.problem.pattern
        event_problem_ids.add(event.problem_id)
        review_dates.add(timezone.localdate(event.reviewed_at))
        if pattern is not None:
            totals = pattern_totals.setdefault(pattern.id, {
                'id': pattern.id,
                'name': pattern.p_name,
                'confidence_total': 0,
                'review_count': 0,
            })
            totals['confidence_total'] += event.confidence
            totals['review_count'] += 1

    for progress in progress_items:
        if progress.last_reviewed:
            review_dates.add(timezone.localdate(progress.last_reviewed))
        if progress.confidence is None or progress.problem_id in event_problem_ids:
            continue
        pattern = progress.problem.pattern
        if pattern is None:
            continue
        totals = pattern_totals.setdefault(pattern.id, {
            'id': pattern.id,
            'name': pattern.p_name,
            'confidence_total': 0,
            'review_count': 0,
        })
        totals['confidence_total'] += progress.confidence
        totals['review_count'] += 1

    patterns = [
        {
            'id': totals['id'],
            'name': totals['name'],
            'average_confidence': round(totals['confidence_total'] / totals['review_count'], 2),
            'review_count': totals['review_count'],
        }
        for totals in pattern_totals.values()
    ]
    patterns.sort(key=lambda item: item['average_confidence'])
    strongest_pattern = max(
        patterns,
        key=lambda item: (item['average_confidence'], item['name'].lower()),
        default=None,
    ) if len(patterns) >= 2 else None
    weakest_pattern = min(
        patterns,
        key=lambda item: (item['average_confidence'], item['name'].lower()),
        default=None,
    ) if len(patterns) >= 2 else None

    today = timezone.localdate(now)
    streak, _ = _review_streaks(review_dates, today)

    due_query = UserProblem.objects.filter(user=user, solved=True, next_revision__lte=now)
    completed_due_reviews = events.filter(scheduled_for__gte=week_start, scheduled_for__lte=now).count()
    pending_due_reviews = due_query.filter(next_revision__gte=week_start).count()
    due_review_total = completed_due_reviews + pending_due_reviews
    completion_rate = round(completed_due_reviews * 100 / due_review_total) if due_review_total else 0

    return Response({
        'problems_solved': progress_items.count(),
        'problems_tracked': UserProblemProgress.objects.filter(user=user, is_tracked=True).count(),
        'problems_due_today': due_query.count(),
        'revision_streak': streak,
        'strongest_pattern': strongest_pattern,
        'weakest_pattern': weakest_pattern,
        'pattern_analysis': patterns,
        'revision_completion_rate': completion_rate,
        'completion_window_days': 7,
    })


def _pattern_trends(user):
    reviews_by_pattern = {}
    reviews = ReviewEvent.objects.filter(
        user=user,
        problem__pattern__isnull=False,
    ).annotate(
        review_rank=Window(
            expression=RowNumber(),
            partition_by=[F('problem__pattern_id')],
            order_by=[F('reviewed_at').desc(), F('id').desc()],
        ),
    ).filter(
        review_rank__lte=6,
    ).order_by(
        'problem__pattern_id',
        'review_rank',
    ).values_list(
        'problem__pattern_id',
        'confidence',
    )
    for pattern_id, confidence in reviews.iterator():
        reviews_by_pattern.setdefault(pattern_id, []).append(confidence)

    trends = {}
    for pattern_id, ratings in reviews_by_pattern.items():
        if len(ratings) < 6:
            trends[pattern_id] = 'steady'
            continue
        recent_average = sum(ratings[:3]) / 3
        previous_average = sum(ratings[3:6]) / 3
        if recent_average - previous_average > 0.15:
            trends[pattern_id] = 'improving'
        elif previous_average - recent_average > 0.15:
            trends[pattern_id] = 'declining'
        else:
            trends[pattern_id] = 'steady'
    return trends


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pattern_strength(request):
    user_progress = UserProblemProgress.objects.filter(
        user=request.user,
        is_tracked=True,
    )
    pattern_rows = list(Pattern.objects.annotate(
        total_problems=Count(
            'problems__sm2_progress',
            filter=Q(
                problems__sm2_progress__user=request.user,
                problems__sm2_progress__is_tracked=True,
            ),
            distinct=True,
        ),
        average_confidence=Avg(
            'problems__sm2_progress__confidence_rating',
            filter=Q(
                problems__sm2_progress__user=request.user,
                problems__sm2_progress__is_tracked=True,
                problems__sm2_progress__confidence_rating__gt=0,
            ),
        ),
    ).order_by('p_name'))
    summary = user_progress.aggregate(
        total_problems=Count('id'),
        average_confidence=Avg('confidence_rating', filter=Q(confidence_rating__gt=0)),
    )
    trends = _pattern_trends(request.user)
    patterns = [
        {
            'pattern_id': pattern.id,
            'pattern_name': pattern.p_name,
            'average_confidence': round(pattern.average_confidence, 2) if pattern.average_confidence is not None else None,
            'total_problems': pattern.total_problems,
            'trend': trends.get(pattern.id, 'steady'),
        }
        for pattern in pattern_rows
    ]
    ranked_patterns = [pattern for pattern in patterns if pattern['average_confidence'] is not None]
    ranked_patterns.sort(key=lambda pattern: (-pattern['average_confidence'], pattern['pattern_name'].lower()))
    response_data = {
        'patterns': patterns,
        'strongest': ranked_patterns[:3],
        'weakest': sorted(
            ranked_patterns,
            key=lambda pattern: (pattern['average_confidence'], pattern['pattern_name'].lower()),
        )[:3],
        'summary': {
            'total_problems': summary['total_problems'],
            'average_confidence': round(summary['average_confidence'], 2) if summary['average_confidence'] is not None else None,
        },
    }
    return Response(PatternStrengthResponseSerializer(response_data).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recommendations(request):
    user = request.user
    now = timezone.now()
    cutoff = now - timedelta(days=7)
    pattern_rows = list(Pattern.objects.annotate(
        total_problems=Count(
            'problems__sm2_progress',
            filter=Q(
                problems__sm2_progress__user=user,
                problems__sm2_progress__is_tracked=True,
            ),
            distinct=True,
        ),
        average_confidence=Avg(
            'problems__sm2_progress__confidence_rating',
            filter=Q(
                problems__sm2_progress__user=user,
                problems__sm2_progress__is_tracked=True,
                problems__sm2_progress__confidence_rating__gt=0,
            ),
        ),
    ).order_by('p_name'))
    pattern_by_id = {pattern.id: pattern for pattern in pattern_rows}
    tracked_progress = list(UserProblemProgress.objects.filter(
        user=user,
        is_tracked=True,
    ).select_related('problem'))
    progress_by_pattern = {}
    for progress in tracked_progress:
        pattern_id = progress.problem.pattern_id
        if pattern_id is not None:
            progress_by_pattern.setdefault(pattern_id, []).append(progress)

    recommendations_list = []

    def add_recommendation(kind, title, description, priority, pattern_id, pattern_name, problem_ids, action_label):
        recommendations_list.append({
            'type': kind,
            'title': title,
            'description': description,
            'priority': priority,
            'pattern_id': pattern_id,
            'pattern_name': pattern_name,
            'problem_ids': problem_ids,
            'action_label': action_label,
        })

    for pattern in pattern_rows:
        if pattern.average_confidence is not None and pattern.average_confidence < 3:
            ids = [
                progress.problem_id
                for progress in progress_by_pattern.get(pattern.id, [])
                if 0 < progress.confidence_rating < 3
            ][:5]
            if ids:
                add_recommendation(
                    'weak_pattern',
                    f'Review {pattern.p_name}',
                    f'Your average confidence is {pattern.average_confidence:.1f}/5 for this pattern.',
                    2,
                    pattern.id,
                    pattern.p_name,
                    ids,
                    'Review weak problems',
                )

    overdue_by_pattern = {}
    for progress in UserProblemProgress.objects.filter(
        user=user,
        is_tracked=True,
        next_review_date__lt=cutoff,
    ).select_related('problem__pattern').order_by('next_review_date'):
        pattern = progress.problem.pattern
        pattern_id = pattern.id if pattern else None
        pattern_name = pattern.p_name if pattern else 'Uncategorized'
        group = overdue_by_pattern.setdefault((pattern_id, pattern_name), [])
        group.append(progress.problem_id)
    for (pattern_id, pattern_name), problem_ids in overdue_by_pattern.items():
        add_recommendation(
            'overdue',
            f'Review overdue {pattern_name} problems',
            f'{len(problem_ids)} problem{"" if len(problem_ids) == 1 else "s"} overdue by more than 7 days.',
            1,
            pattern_id,
            pattern_name,
            problem_ids[:5],
            'Review overdue problems',
        )

    trends = _pattern_trends(user)
    for pattern_id, trend in trends.items():
        if trend == 'declining':
            pattern = pattern_by_id.get(pattern_id)
            if pattern is None:
                continue
            ids = [progress.problem_id for progress in progress_by_pattern.get(pattern_id, [])][:5]
            if ids:
                add_recommendation(
                    'declining',
                    f'Confidence is declining in {pattern.p_name}',
                    'Your last 3 reviews averaged lower than the 3 before them.',
                    2,
                    pattern.id,
                    pattern.p_name,
                    ids,
                    'Practice this pattern',
                )

    tracked_problem = UserProblemProgress.objects.filter(
        user=user,
        problem_id=OuterRef('pk'),
        is_tracked=True,
    )
    unstarted_problem_ids = {}
    for pattern_id, problem_id in Problem.objects.filter(
        pattern_id__isnull=False,
    ).annotate(
        is_tracked=Exists(tracked_problem),
    ).filter(
        is_tracked=False,
    ).order_by('id').values_list('pattern_id', 'id'):
        problem_ids = unstarted_problem_ids.setdefault(pattern_id, [])
        if len(problem_ids) < 5:
            problem_ids.append(problem_id)

    for pattern in pattern_rows:
        if pattern.total_problems != 0:
            continue
        problem_ids = unstarted_problem_ids.get(pattern.id, [])
        if problem_ids:
            add_recommendation(
                'not_started',
                f'Start {pattern.p_name}',
                f'You have not added any {pattern.p_name} problems to your review plan.',
                3,
                pattern.id,
                pattern.p_name,
                problem_ids,
                'Explore these problems',
            )

    all_problem_ids = {
        problem_id
        for recommendation in recommendations_list
        for problem_id in recommendation['problem_ids']
    }
    problems_by_id = {
        problem['id']: problem
        for problem in Problem.objects.filter(id__in=all_problem_ids).values('id', 'title', 'difficulty', 'link')
    }
    for recommendation in recommendations_list:
        recommendation['problems'] = [
            problems_by_id[problem_id]
            for problem_id in recommendation['problem_ids']
            if problem_id in problems_by_id
        ]

    recommendations_list.sort(key=lambda item: (item['priority'], item['title'].lower()))
    return Response(RecommendationSerializer(recommendations_list, many=True).data)


def _daily_review_window(days):
    today = timezone.localdate()
    first_day = today - timedelta(days=days - 1)
    start = timezone.make_aware(datetime.combine(first_day, time.min), timezone.get_current_timezone())
    end = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), timezone.get_current_timezone())
    return first_day, today, start, end


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def activity_heatmap(request):
    first_day, today, start, end = _daily_review_window(90)
    counts = {
        row['review_day']: row['count']
        for row in ReviewEvent.objects.filter(
            user=request.user,
            reviewed_at__gte=start,
            reviewed_at__lt=end,
        ).annotate(review_day=TruncDate('reviewed_at')).values('review_day').annotate(
            count=Count('id'),
        ).order_by('review_day')
    }
    data = [
        {'date': first_day + timedelta(days=offset), 'count': counts.get(first_day + timedelta(days=offset), 0)}
        for offset in range((today - first_day).days + 1)
    ]
    return Response(ActivityHeatmapDaySerializer(data, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def confidence_trend(request):
    first_day, today, start, end = _daily_review_window(30)
    averages = {
        row['review_day']: row
        for row in ReviewEvent.objects.filter(
            user=request.user,
            reviewed_at__gte=start,
            reviewed_at__lt=end,
        ).annotate(review_day=TruncDate('reviewed_at')).values('review_day').annotate(
            average_confidence=Avg('confidence'),
            review_count=Count('id'),
        ).order_by('review_day')
    }
    data = []
    for offset in range((today - first_day).days + 1):
        review_day = first_day + timedelta(days=offset)
        row = averages.get(review_day)
        data.append({
            'date': review_day,
            'average_confidence': round(row['average_confidence'], 2) if row else None,
            'review_count': row['review_count'] if row else 0,
        })
    return Response(ConfidenceTrendDaySerializer(data, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def mark_problem_solved(request, problem_id):
    try:
        problem = Problem.objects.get(id=problem_id)
    except Problem.DoesNotExist:
        return Response(
            {'detail': 'Problem not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    confidence = request.data.get('confidence')
    if confidence is None:
        confidence = 3

    try:
        confidence = int(confidence)
    except (TypeError, ValueError):
        return Response(
            {'detail': 'Confidence must be an integer between 1 and 5.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if confidence < 1 or confidence > 5:
        return Response(
            {'detail': 'Confidence must be between 1 and 5.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    progress, _ = UserProblem.objects.get_or_create(
        user=request.user,
        problem=problem,
    )

    reviewed_at = timezone.now()
    scheduled_for = progress.next_revision if progress.revision_count else None
    progress.solved = True
    progress.confidence = confidence
    progress.last_reviewed = reviewed_at
    progress.revision_count = (progress.revision_count or 0) + 1
    progress.next_revision = next_revision_for(
        confidence=confidence,
        difficulty=problem.difficulty,
        revision_count=progress.revision_count - 1,
    )
    progress.save()
    ReviewEvent.objects.create(
        user=request.user,
        problem=problem,
        confidence=confidence,
        scheduled_for=scheduled_for,
        reviewed_at=reviewed_at,
    )

    return Response(UserProblemSerializer(progress).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response(
            {'detail': 'A refresh token is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        RefreshToken(refresh_token).blacklist()
    except Exception:
        return Response(
            {'detail': 'Invalid or expired refresh token.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(status=status.HTTP_205_RESET_CONTENT)
    