from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Assessment, Problem, UserProblem, UserProblemProgress, UserSettings
from .services import generate_weekly_assessment


class UserProfileAndSettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='profile-user',
            email='profile@example.com',
            password='secure-password-123',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_profile_get_includes_joined_date_and_learning_stats(self):
        problem = Problem.objects.create(
            title='Two Sum',
            leetcode_id=990101,
            link='https://leetcode.com/problems/two-sum/',
            difficulty='Easy',
        )
        UserProblem.objects.create(user=self.user, problem=problem, solved=True)
        Assessment.objects.create(user=self.user, status='completed')

        response = self.client.get('/api/users/profile/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['stats'], {
            'problems_solved': 1,
            'problems_tracked': 0,
            'assessments_completed': 1,
        })
        self.assertEqual(response.json()['email'], 'profile@example.com')
        self.assertIn('date_joined', response.json())

    def test_profile_put_updates_username_and_email(self):
        response = self.client.put('/api/users/profile/', {
            'username': 'updated-user',
            'email': 'updated@example.com',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'updated-user')
        self.assertEqual(self.user.email, 'updated@example.com')

    def test_settings_are_created_with_defaults_and_validated(self):
        response = self.client.get('/api/users/settings/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['daily_problem_goal'], 3)
        self.assertEqual(response.json()['assessment_day'], 'sunday')
        self.assertTrue(UserSettings.objects.filter(user=self.user).exists())

        invalid_response = self.client.put('/api/users/settings/', {
            'daily_problem_goal': 0,
            'assessment_day': 'funday',
            'assessment_time_limit': 200,
            'timezone': 'Not/A_Timezone',
        }, format='json')

        self.assertEqual(invalid_response.status_code, 400)
        self.assertIn('daily_problem_goal', invalid_response.json())
        self.assertIn('assessment_day', invalid_response.json())
        self.assertIn('timezone', invalid_response.json())

    def test_settings_update_persists_preferences(self):
        response = self.client.put('/api/users/settings/', {
            'daily_problem_goal': 5,
            'assessment_day': 'friday',
            'assessment_time_limit': 45,
            'email_reminders': False,
            'reminder_time': '08:30',
            'theme': 'dark',
            'timezone': 'America/New_York',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        settings_record = UserSettings.objects.get(user=self.user)
        self.assertEqual(settings_record.daily_problem_goal, 5)
        self.assertEqual(settings_record.assessment_day, 'friday')
        self.assertFalse(settings_record.email_reminders)
        self.assertEqual(settings_record.leetcode_username, '')

    def test_settings_cannot_bypass_leetcode_profile_validation(self):
        response = self.client.put('/api/users/settings/', {
            'leetcode_username': 'ada_codes',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(UserSettings.objects.filter(user=self.user, leetcode_username='ada_codes').exists())

    def test_change_password_checks_current_password_and_updates_hash(self):
        invalid_response = self.client.post('/api/users/change-password/', {
            'current_password': 'not-the-password',
            'new_password': 'new-secure-password-456',
        }, format='json')
        self.assertEqual(invalid_response.status_code, 400)

        response = self.client.post('/api/users/change-password/', {
            'current_password': 'secure-password-123',
            'new_password': 'new-secure-password-456',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('new-secure-password-456'))

    def test_delete_account_requires_password(self):
        response = self.client.delete('/api/users/delete-account/', {'password': 'incorrect'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

        response = self.client.delete('/api/users/delete-account/', {'password': 'secure-password-123'}, format='json')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_disconnect_leetcode_clears_username_and_sync_timestamp(self):
        settings_record = UserSettings.objects.create(
            user=self.user,
            leetcode_username='ada_codes',
            leetcode_last_synced_at=timezone.now(),
        )

        response = self.client.post('/api/users/disconnect-leetcode/')

        self.assertEqual(response.status_code, 200)
        settings_record.refresh_from_db()
        self.assertEqual(settings_record.leetcode_username, '')
        self.assertIsNone(settings_record.leetcode_last_synced_at)

    @patch('revise.views.sync_recent_problems')
    def test_sync_returns_structured_recent_problem_result(self, sync_recent):
        UserSettings.objects.create(user=self.user, leetcode_username='ada_codes')
        sync_recent.return_value = {
            'success': True,
            'username': 'ada_codes',
            'fetched': 1,
            'selected': 1,
            'added': 1,
            'already_tracked': 0,
            'last_synced_at': timezone.now(),
            'message': 'LeetCode synchronization completed',
            'problems': [],
        }

        response = self.client.post('/api/leetcode/sync/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['imported_count'], 1)
        self.assertEqual(response.json()['selected'], 1)
        sync_recent.assert_called_once()

    def test_assessment_uses_the_users_configured_duration(self):
        UserSettings.objects.create(user=self.user, assessment_time_limit=45)
        for index in range(5):
            problem = Problem.objects.create(
                title=f'Problem {index}',
                leetcode_id=990200 + index,
                link=f'https://leetcode.com/problems/problem-{index}/',
                difficulty='Easy',
            )
            UserProblemProgress.objects.create(user=self.user, problem=problem)

        assessment = generate_weekly_assessment(self.user)

        self.assertEqual(assessment.time_limit_minutes, 45)
