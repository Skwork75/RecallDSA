from django.db import migrations


PROBLEMS = [
    {
        'title': 'Kth Smallest Element in a BST',
        'leetcode_id': 230,
        'link': 'https://leetcode.com/problems/kth-smallest-element-in-a-bst/',
        'difficulty': 'Medium',
        'pattern': 'BST',
    },
    {
        'title': 'Binary Search',
        'leetcode_id': 704,
        'link': 'https://leetcode.com/problems/binary-search/',
        'difficulty': 'Easy',
        'pattern': 'Binary Search',
    },
    {
        'title': 'Longest Substring Without Repeating Characters',
        'leetcode_id': 3,
        'link': 'https://leetcode.com/problems/longest-substring-without-repeating-characters/',
        'difficulty': 'Medium',
        'pattern': 'Sliding Window',
    },
]


def seed_problems(apps, schema_editor):
    Pattern = apps.get_model('revise', 'Pattern')
    Problem = apps.get_model('revise', 'Problem')

    for problem_data in PROBLEMS:
        pattern_name = problem_data.pop('pattern')
        pattern = Pattern.objects.get(p_name=pattern_name)
        Problem.objects.get_or_create(
            leetcode_id=problem_data['leetcode_id'],
            defaults={**problem_data, 'pattern': pattern},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('revise', '0005_problem_userproblem_seed_patterns'),
    ]

    operations = [
        migrations.RunPython(seed_problems, migrations.RunPython.noop),
    ]