from django.db import models

class Solved(models.Model):
    q_id = models.IntegerField()
    q_name = models.CharField(default = str(q_id))
    q_link = models.TextField()

    def __str__(self):
        return self.q_name
class Pattern(models.Model):
    p_name = models.CharField(max_length=100)

    def __str__(self):
        return self.p_name
