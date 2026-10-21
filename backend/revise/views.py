from datetime import timedelta
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Avg, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import (
    ProblemSerializer,
    RegisterSerializer,
    UserProblemSerializer,
    UserSerializer,
    DSASheetSerializer,
    DSASheetProblemSerializer,
)
from .models import Problem, ReviewEvent, UserProblem, DSASheet, DSASheetProblem, Pattern, UserProblemProgress
from .sm2 import calculate_next_review
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
def dsasheets(request):
    sheets = DSASheet.objects.filter(
        problems__isnull=False,
    ).distinct().prefetch_related('problems__problem__sm2_progress')
    if request.query_params.get('featured', '').lower() in ('1', 'true'):
        sheets = sheets.filter(is_featured=True)
    return Response(DSASheetSerializer(sheets, many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dsasheet_detail(request, slug):
    try:
        sheet = DSASheet.objects.prefetch_related(
            'problems__problem__pattern',
            'problems__problem__patterns',
            'problems__problem__sm2_progress',
        ).filter(problems__isnull=False).distinct().get(slug=slug)
    except DSASheet.DoesNotExist:
        return Response({'detail': 'Sheet not found.'}, status=status.HTTP_404_NOT_FOUND)

    serialized_problems = DSASheetProblemSerializer(
        sheet.problems.select_related('problem__pattern').prefetch_related('problem__patterns'),
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
    strongest_pattern = max(patterns, key=lambda item: item['average_confidence'], default=None)
    weakest_pattern = min(patterns, key=lambda item: item['average_confidence'], default=None)

    today = timezone.localdate(now)
    streak = 0
    streak_day = today if today in review_dates else today - timedelta(days=1)
    while streak_day in review_dates:
        streak += 1
        streak_day -= timedelta(days=1)

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
    