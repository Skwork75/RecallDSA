from django.contrib import admin
from .models import Pattern, Problem, Solved, UserProblem

admin.site.register(Solved)
admin.site.register(Pattern)
admin.site.register(Problem)
admin.site.register(UserProblem)