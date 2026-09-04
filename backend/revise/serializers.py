from .models import Pattern, Problem, Solved, UserProblem
from rest_framework import serializers

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

    class Meta:
        model = Problem
        fields = ['id', 'title', 'leetcode_id', 'link', 'difficulty', 'pattern']


class UserProblemSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProblem
        fields = '__all__'
