from django.shortcuts import render
from rest_framework.decorators import api_view
from .serializers import SolvedSerializer
from .models import Solved
from rest_framework.response import Response
from rest_framework import status

@api_view(["GET"])
def home(request):
    questions = Solved.objects.all()
    serializer = SolvedSerializer(questions, many=True)
    return Response(serializer.data)
    