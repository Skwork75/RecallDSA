from .models import (
    Assessment,
    AssessmentProblem,
    Pattern,
    Problem,
    Solved,
    UserProblem,
    GlobalProblem,
    DSASheet,
    DSASheetProblem,
)
from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class SolvedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Solved
        fields = '__all__'


class PatternSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pattern
        fields = ['id', 'p_name']


class ProblemSerializer(serializers.ModelSerializer):
    pattern = PatternSerializer(read_only=True)
    patterns = PatternSerializer(read_only=True, many=True)

    class Meta:
        model = Problem
        fields = ['id', 'slug', 'title', 'leetcode_id', 'link', 'difficulty', 'pattern', 'patterns', 'description', 'created_at']


class GlobalProblemSerializer(serializers.ModelSerializer):
    pattern = PatternSerializer(read_only=True)

    class Meta:
        model = GlobalProblem
        fields = ['id', 'slug', 'title', 'leetcode_id', 'link', 'difficulty', 'pattern', 'description']


class UserProblemSerializer(serializers.ModelSerializer):
    problem = ProblemSerializer(read_only=True)

    class Meta:
        model = UserProblem
        fields = ['id', 'problem', 'solved', 'confidence', 'last_reviewed', 'next_revision', 'revision_count', 'interval', 'source']


class DSASheetSerializer(serializers.ModelSerializer):
    tracked_count = serializers.SerializerMethodField()
    total_problems = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = DSASheet
        fields = [
            'id', 'title', 'slug', 'description', 'author', 'total_problems',
            'cover_image_url', 'is_featured', 'tracked_count', 'progress', 'created_at',
        ]

    def get_total_problems(self, sheet):
        if hasattr(sheet, 'sheet_problem_count'):
            return sheet.sheet_problem_count
        return sheet.problems.count()

    def get_tracked_count(self, sheet):
        if hasattr(sheet, 'sheet_tracked_count'):
            return sheet.sheet_tracked_count
        user = self.context.get('request').user if self.context.get('request') else None
        if not user or not user.is_authenticated:
            return 0
        return sheet.problems.filter(
            problem__sm2_progress__user=user,
            problem__sm2_progress__is_tracked=True,
        ).count()

    def get_progress(self, sheet):
        total = self.get_total_problems(sheet)
        tracked = self.get_tracked_count(sheet)
        return {'tracked': tracked, 'total': total}


class DSASheetProblemSerializer(serializers.ModelSerializer):
    problem = ProblemSerializer(read_only=True)
    is_tracked_by_user = serializers.BooleanField(read_only=True)

    class Meta:
        model = DSASheetProblem
        fields = ['id', 'sheet', 'problem', 'order', 'category', 'is_tracked_by_user']


class AssessmentProblemSerializer(serializers.ModelSerializer):
    problem = ProblemSerializer(read_only=True)

    class Meta:
        model = AssessmentProblem
        fields = ['id', 'problem', 'status', 'answered_at']


class AssessmentSerializer(serializers.ModelSerializer):
    problems = AssessmentProblemSerializer(many=True, read_only=True)
    pattern_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id',
            'created_at',
            'time_limit_minutes',
            'status',
            'started_at',
            'completed_at',
            'score_percentage',
            'total_problems',
            'problems',
            'pattern_breakdown',
        ]

    def get_pattern_breakdown(self, assessment):
        breakdown = {}
        for entry in assessment.problems.all():
            pattern = entry.problem.pattern
            name = pattern.p_name if pattern else 'Uncategorized'
            totals = breakdown.setdefault(name, {'name': name, 'solved': 0, 'total': 0})
            totals['total'] += 1
            totals['solved'] += int(entry.status == 'solved')
        return list(breakdown.values())
