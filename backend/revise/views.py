from datetime import timedelta
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import ProblemSerializer, RegisterSerializer, UserProblemSerializer, UserSerializer
from .models import Problem, UserProblem
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

@api_view(["GET"])
def home(request):
    questions = Problem.objects.select_related('pattern').all()
    serializer = ProblemSerializer(questions, many=True)
    return Response(serializer.data)


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
    ).select_related('problem__pattern').order_by('confidence', 'next_revision')

    due_or_weak = [
        item for item in problems
        if item.next_revision is None or item.next_revision <= now or (item.confidence is not None and item.confidence <= 2)
    ]

    if not due_or_weak:
        due_or_weak = list(problems[:5])

    return Response(UserProblemSerializer(due_or_weak[:5], many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
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

    progress.solved = True
    progress.confidence = confidence
    progress.last_reviewed = timezone.now()
    progress.revision_count = (progress.revision_count or 0) + 1
    progress.next_revision = next_revision_for(
        confidence=confidence,
        difficulty=problem.difficulty,
        revision_count=progress.revision_count - 1,
    )
    progress.save()

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
    