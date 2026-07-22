from .models import Solved
from rest_framework import serializers

class SolvedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Solved
        fields = '__all__'
