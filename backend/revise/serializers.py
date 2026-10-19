from .models import Pattern, Problem, Solved, UserProblem, GlobalProblem, DSASheet, DSASheetProblem
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
    class Meta:
        model = DSASheet
        fields = ['id', 'name', 'description', 'created_at']


class DSASheetProblemSerializer(serializers.ModelSerializer):
    problem = ProblemSerializer(read_only=True)

    class Meta:
        model = DSASheetProblem
        fields = ['id', 'sheet', 'problem']
