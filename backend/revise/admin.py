from django.contrib import admin
from .models import Assessment, AssessmentProblem, DSASheet, DSASheetProblem, Pattern, Problem, Solved, UserProblem, UserSettings

admin.site.register(Solved)
admin.site.register(Pattern)
admin.site.register(Problem)
admin.site.register(UserProblem)
admin.site.register(DSASheet)
admin.site.register(DSASheetProblem)
admin.site.register(Assessment)
admin.site.register(AssessmentProblem)
admin.site.register(UserSettings)