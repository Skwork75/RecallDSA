from django.shortcuts import render
from rest_framework.decorators import api_view
from .serializers import ProblemSerializer
from .models import Problem
from rest_framework.response import Response
from rest_framework import status

@api_view(["GET"])
def home(request):
    questions = Problem.objects.select_related('pattern').all()
    serializer = ProblemSerializer(questions, many=True)
    return Response(serializer.data)
    