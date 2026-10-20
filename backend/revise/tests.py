from datetime import timedelta
from io import StringIO
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from .models import DSASheet, DSASheetProblem, Pattern, Problem, ReviewEvent, UserProblem, UserProblemProgress
from .sm2 import calculate_next_review


class AuthenticationTests(APITestCase):
	def test_register_login_current_user_and_logout(self):
		register_response = self.client.post('/api/auth/register/', {
			'username': 'ada',
			'email': 'ada@example.com',
			'password': 'secure-password-123',
		}, format='json')

		self.assertEqual(register_response.status_code, 201)
		tokens = register_response.json()
		self.assertIn('access', tokens)
		self.assertIn('refresh', tokens)

		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
		me_response = self.client.get('/api/auth/me/')
		self.assertEqual(me_response.status_code, 200)
		self.assertEqual(me_response.json()['username'], 'ada')

		logout_response = self.client.post('/api/auth/logout/', {
			'refresh': tokens['refresh'],
		}, format='json')
		self.assertEqual(logout_response.status_code, 205)

		refresh_response = self.client.post('/api/token/refresh/', {
			'refresh': tokens['refresh'],
		}, format='json')
		self.assertEqual(refresh_response.status_code, 401)

	def test_login_rejects_invalid_credentials(self):
		get_user_model().objects.create_user(
			username='ada',
			password='secure-password-123',
		)

		response = self.client.post('/api/auth/login/', {
			'username': 'ada',
			'password': 'wrong-password',
		}, format='json')

		self.assertEqual(response.status_code, 401)

	def test_user_can_mark_problem_solved_and_view_profile(self):
		user = get_user_model().objects.create_user(username='ada', password='secure-password-123')
		pattern = Pattern.objects.create(p_name='Binary Search')
		problem = Problem.objects.create(
			title='Binary Search',
			leetcode_id=99999,
			link='https://leetcode.com/problems/binary-search/',
			difficulty='Easy',
			pattern=pattern,
		)
		refresh = RefreshToken.for_user(user)
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

		solve_response = self.client.post(f'/api/problems/{problem.id}/solve/', {'confidence': 4}, format='json')
		self.assertEqual(solve_response.status_code, 200)
		self.assertTrue(solve_response.json()['solved'])
		self.assertEqual(solve_response.json()['confidence'], 4)
		self.assertIsNotNone(solve_response.json()['next_revision'])
		self.assertEqual(UserProblem.objects.filter(user=user, problem=problem).count(), 1)

		profile_response = self.client.get('/api/auth/profile/')
		self.assertEqual(profile_response.status_code, 200)
		self.assertEqual(len(profile_response.json()['solved_problems']), 1)
		self.assertEqual(profile_response.json()['solved_problems'][0]['problem']['title'], 'Binary Search')

	def test_review_confidence_schedules_next_revision(self):
		user = get_user_model().objects.create_user(username='carl', password='secure-password-123')
		pattern = Pattern.objects.create(p_name='Dynamic Programming')
		problem = Problem.objects.create(
			title='Climbing Stairs',
			leetcode_id=70,
			link='https://leetcode.com/problems/climbing-stairs/',
			difficulty='Easy',
			pattern=pattern,
		)
		refresh = RefreshToken.for_user(user)
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

		response = self.client.post(f'/api/problems/{problem.id}/solve/', {'confidence': 1}, format='json')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['confidence'], 1)
		self.assertEqual(response.json()['revision_count'], 1)
		self.assertIsNotNone(response.json()['next_revision'])

		user_problem = UserProblem.objects.get(user=user, problem=problem)
		self.assertTrue(user_problem.solved)
		self.assertEqual(user_problem.confidence, 1)
		self.assertIsNotNone(user_problem.next_revision)
		self.assertEqual(ReviewEvent.objects.filter(user=user, problem=problem).count(), 1)

	def test_today_revisions_returns_due_items_for_logged_user(self):
		user = get_user_model().objects.create_user(username='dana', password='secure-password-123')
		other_user = get_user_model().objects.create_user(username='zoe', password='secure-password-123')
		pattern = Pattern.objects.create(p_name='Hash Map')
		problem = Problem.objects.create(
			title='Two Sum',
			leetcode_id=1,
			link='https://leetcode.com/problems/two-sum/',
			difficulty='Easy',
			pattern=pattern,
		)
		other_problem = Problem.objects.create(
			title='Group Anagrams',
			leetcode_id=49,
			link='https://leetcode.com/problems/group-anagrams/',
			difficulty='Medium',
			pattern=pattern,
		)
		UserProblem.objects.create(user=user, problem=problem, solved=True, next_revision=timezone.now() - timedelta(days=1), revision_count=1)
		UserProblem.objects.create(user=user, problem=other_problem, solved=True, next_revision=timezone.now() + timedelta(days=2), revision_count=1)
		UserProblem.objects.create(user=other_user, problem=problem, solved=True, next_revision=timezone.now() - timedelta(days=1), revision_count=1)

		refresh = RefreshToken.for_user(user)
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

		response = self.client.get('/api/revisions/today/')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json()), 1)
		self.assertEqual(response.json()[0]['problem']['title'], 'Two Sum')

	def test_weekly_assessment_returns_low_confidence_and_due_items_for_logged_user(self):
		user = get_user_model().objects.create_user(username='erin', password='secure-password-123')
		other_user = get_user_model().objects.create_user(username='frank', password='secure-password-123')
		pattern = Pattern.objects.create(p_name='Greedy')
		weak_problem = Problem.objects.create(
			title='Candy',
			leetcode_id=135,
			link='https://leetcode.com/problems/candy/',
			difficulty='Medium',
			pattern=pattern,
		)
		due_problem = Problem.objects.create(
			title='Jump Game',
			leetcode_id=55,
			link='https://leetcode.com/problems/jump-game/',
			difficulty='Hard',
			pattern=pattern,
		)
		other_problem = Problem.objects.create(
			title='Best Time to Buy and Sell Stock',
			leetcode_id=121,
			link='https://leetcode.com/problems/best-time-to-buy-and-sell-stock/',
			difficulty='Easy',
			pattern=pattern,
		)
		UserProblem.objects.create(user=user, problem=weak_problem, solved=True, confidence=1, next_revision=timezone.now() - timedelta(days=2), revision_count=3)
		UserProblem.objects.create(user=user, problem=due_problem, solved=True, confidence=3, next_revision=timezone.now() - timedelta(days=1), revision_count=2)
		UserProblem.objects.create(user=user, problem=other_problem, solved=True, confidence=5, next_revision=timezone.now() + timedelta(days=10), revision_count=4)
		UserProblem.objects.create(user=other_user, problem=weak_problem, solved=True, confidence=1, next_revision=timezone.now() - timedelta(days=2), revision_count=3)

		refresh = RefreshToken.for_user(user)
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

		response = self.client.get('/api/assessments/weekly/')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json()), 2)
		self.assertEqual([item['problem']['title'] for item in response.json()], ['Candy', 'Jump Game'])

	def test_dashboard_returns_personal_review_and_pattern_metrics(self):
		user = get_user_model().objects.create_user(username='grace', password='secure-password-123')
		other_user = get_user_model().objects.create_user(username='heidi', password='secure-password-123')
		strong_pattern = Pattern.objects.create(p_name='Sliding Window')
		weak_pattern = Pattern.objects.create(p_name='Dynamic Programming')
		strong_problem = Problem.objects.create(
			title='Longest Substring',
			leetcode_id=910003,
			link='https://leetcode.com/problems/longest-substring-without-repeating-characters/',
			difficulty='Medium',
			pattern=strong_pattern,
		)
		weak_problem = Problem.objects.create(
			title='Climbing Stairs',
			leetcode_id=910070,
			link='https://leetcode.com/problems/climbing-stairs/',
			difficulty='Easy',
			pattern=weak_pattern,
		)
		pending_problem = Problem.objects.create(
			title='House Robber',
			leetcode_id=910198,
			link='https://leetcode.com/problems/house-robber/',
			difficulty='Medium',
			pattern=weak_pattern,
		)
		now = timezone.now()
		yesterday = now - timedelta(days=1)
		UserProblem.objects.create(user=user, problem=strong_problem, solved=True, confidence=4, next_revision=now + timedelta(days=5), revision_count=2)
		UserProblem.objects.create(user=user, problem=weak_problem, solved=True, confidence=1, next_revision=now + timedelta(days=4), revision_count=2)
		UserProblem.objects.create(user=user, problem=pending_problem, solved=True, confidence=2, next_revision=now - timedelta(days=1), revision_count=1)
		UserProblem.objects.create(user=other_user, problem=strong_problem, solved=True, confidence=5, next_revision=now - timedelta(days=1), revision_count=1)
		ReviewEvent.objects.create(user=user, problem=strong_problem, confidence=5, scheduled_for=now - timedelta(days=3), reviewed_at=now)
		ReviewEvent.objects.create(user=user, problem=strong_problem, confidence=4, reviewed_at=yesterday)
		ReviewEvent.objects.create(user=user, problem=weak_problem, confidence=1, reviewed_at=now)
		ReviewEvent.objects.create(user=user, problem=weak_problem, confidence=2, reviewed_at=yesterday)
		ReviewEvent.objects.create(user=other_user, problem=strong_problem, confidence=1, reviewed_at=now)

		refresh = RefreshToken.for_user(user)
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
		response = self.client.get('/api/dashboard/')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['problems_solved'], 3)
		self.assertEqual(response.json()['problems_due_today'], 1)
		self.assertEqual(response.json()['revision_streak'], 2)
		self.assertEqual(response.json()['revision_completion_rate'], 50)
		self.assertEqual(response.json()['strongest_pattern']['name'], 'Sliding Window')
		self.assertEqual(response.json()['strongest_pattern']['average_confidence'], 4.5)
		self.assertEqual(response.json()['weakest_pattern']['name'], 'Dynamic Programming')
		self.assertEqual(response.json()['weakest_pattern']['average_confidence'], 1.67)

	def test_dashboard_requires_authentication(self):
		response = self.client.get('/api/dashboard/')
		self.assertEqual(response.status_code, 401)


class SM2CalculatorTests(APITestCase):
	def test_first_review_uses_initial_interval(self):
		result = calculate_next_review(confidence=4, difficulty='Easy', ef=2.5, interval=0, rep_number=0)
		self.assertEqual(result['interval'], 1)
		self.assertEqual(result['repetition_number'], 1)
		self.assertGreaterEqual(result['easiness_factor'], 1.3)

	def test_failed_review_resets_repetition_and_interval(self):
		result = calculate_next_review(confidence=2, difficulty='Medium', ef=2.5, interval=6, rep_number=2)
		self.assertEqual(result['interval'], 1)
		self.assertEqual(result['repetition_number'], 0)
		self.assertGreaterEqual(result['easiness_factor'], 1.3)

	def test_many_consecutive_successes_grow_interval(self):
		result_1 = calculate_next_review(confidence=5, difficulty='Easy', ef=2.5, interval=0, rep_number=0)
		result_2 = calculate_next_review(confidence=5, difficulty='Easy', ef=result_1['easiness_factor'], interval=result_1['interval'], rep_number=result_1['repetition_number'])
		result_3 = calculate_next_review(confidence=5, difficulty='Easy', ef=result_2['easiness_factor'], interval=result_2['interval'], rep_number=result_2['repetition_number'])
		self.assertEqual(result_1['interval'], 1)
		self.assertGreater(result_2['interval'], result_1['interval'])
		self.assertGreater(result_3['interval'], result_2['interval'])
		self.assertEqual(result_3['repetition_number'], 3)

	def test_submit_review_updates_user_progress(self):
		user = get_user_model().objects.create_user(username='sm2-user', password='secure-password-123')
		problem = Problem.objects.create(
			title='Two Sum',
			leetcode_id=1,
			link='https://leetcode.com/problems/two-sum/',
			difficulty='Easy',
			pattern=Pattern.objects.create(p_name='Hash Map'),
		)
		self.client.force_authenticate(user=user)
		response = self.client.post('/api/revisions/submit-review/', {
			'problem_id': problem.id,
			'confidence_rating': 5,
		}, format='json')
		self.assertEqual(response.status_code, 200)
		self.assertIn('next_review_date', response.json())
		self.assertTrue(UserProblemProgress.objects.filter(user=user, problem=problem).exists())
		self.assertEqual(UserProblemProgress.objects.get(user=user, problem=problem).confidence_rating, 5)


class CuratedSheetTests(APITestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username='sheet-user', password='secure-password-123')
		self.client.force_authenticate(user=self.user)
		self.sheet = DSASheet.objects.create(
			title='Blind 75',
			slug='blind-75-test',
			description='A focused list',
			is_featured=True,
		)
		self.first_problem = Problem.objects.create(
			title='Two Sum',
			leetcode_id=801,
			link='https://leetcode.com/problems/two-sum/',
			difficulty='Easy',
			pattern=Pattern.objects.create(p_name='Hash Map'),
		)
		self.second_problem = Problem.objects.create(
			title='Maximum Subarray',
			leetcode_id=802,
			link='https://leetcode.com/problems/maximum-subarray/',
			difficulty='Medium',
			pattern=Pattern.objects.create(p_name='Dynamic Programming'),
		)
		DSASheetProblem.objects.create(
			sheet=self.sheet,
			problem=self.first_problem,
			order=1,
			category='Arrays & Hashing',
		)
		DSASheetProblem.objects.create(
			sheet=self.sheet,
			problem=self.second_problem,
			order=2,
			category='Dynamic Programming',
		)

	def test_sheet_list_and_detail_include_per_user_progress(self):
		list_response = self.client.get('/api/sheets/')
		self.assertEqual(list_response.status_code, 200)
		sheet_summary = next(sheet for sheet in list_response.json() if sheet['slug'] == 'blind-75-test')
		self.assertEqual(sheet_summary['title'], 'Blind 75')
		self.assertEqual(sheet_summary['progress'], {'tracked': 0, 'total': 2})

		detail_response = self.client.get('/api/sheets/blind-75-test/')
		self.assertEqual(detail_response.status_code, 200)
		self.assertEqual(len(detail_response.json()['categories']), 2)
		problem = detail_response.json()['categories'][0]['problems'][0]
		self.assertFalse(problem['is_tracked_by_user'])
		self.assertEqual(problem['order'], 1)

	def test_track_all_adds_sm2_progress_once(self):
		first_response = self.client.post('/api/sheets/blind-75-test/track-all/', {}, format='json')
		second_response = self.client.post('/api/sheets/blind-75-test/track-all/', {}, format='json')

		self.assertEqual(first_response.status_code, 200)
		self.assertEqual(first_response.json()['added_count'], 2)
		self.assertEqual(second_response.json()['added_count'], 0)
		self.assertEqual(UserProblemProgress.objects.filter(user=self.user, is_tracked=True).count(), 2)

	def test_track_selected_rejects_ids_not_in_sheet(self):
		response = self.client.post(
			'/api/sheets/blind-75-test/track-selected/',
			{'problem_ids': [self.first_problem.id, 999999]},
			format='json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertFalse(UserProblemProgress.objects.filter(user=self.user).exists())

	def test_track_selected_adds_only_requested_problem(self):
		response = self.client.post(
			'/api/sheets/blind-75-test/track-selected/',
			{'problem_ids': [self.second_problem.id]},
			format='json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['added_count'], 1)
		self.assertTrue(UserProblemProgress.objects.filter(user=self.user, problem=self.second_problem, is_tracked=True).exists())
		detail = self.client.get('/api/sheets/blind-75-test/').json()
		tracked_problem = next(
			problem
			for category in detail['categories']
			for problem in category['problems']
			if problem['problem']['id'] == self.second_problem.id
		)
		self.assertTrue(tracked_problem['is_tracked_by_user'])

	def test_track_selected_reactivates_previously_untracked_progress(self):
		UserProblemProgress.objects.create(
			user=self.user,
			problem=self.first_problem,
			is_tracked=False,
		)

		response = self.client.post(
			'/api/sheets/blind-75-test/track-selected/',
			{'problem_ids': [self.first_problem.id]},
			format='json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['added_count'], 1)
		self.assertTrue(UserProblemProgress.objects.get(user=self.user, problem=self.first_problem).is_tracked)

	def test_seed_command_is_repeatable_with_local_sample_json(self):
		fixture = Path(__file__).resolve().parent / 'data' / 'sheets' / 'blind-75.json'
		call_command('seed_sheets', path=fixture, stdout=StringIO())
		call_command('seed_sheets', path=fixture, stdout=StringIO())

		sheet = DSASheet.objects.get(slug='blind-75')
		self.assertEqual(sheet.problems.count(), 5)
		self.assertEqual(sheet.total_problems, 5)
		self.assertTrue(sheet.is_featured)
