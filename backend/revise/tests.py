from datetime import timedelta
from io import StringIO
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from .models import (
	Assessment,
	AssessmentProblem,
	DSASheet,
	DSASheetProblem,
	Pattern,
	Problem,
	ReviewEvent,
	UserProblem,
	UserProblemProgress,
)
from .services import generate_weekly_assessment
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

	def test_submit_review_adds_problem_to_solved_profile_and_dashboard(self):
		user = get_user_model().objects.create_user(username='mira', password='secure-password-123')
		problem = Problem.objects.create(
			title='Two Sum',
			leetcode_id=1,
			link='https://leetcode.com/problems/two-sum/',
			difficulty='Easy',
		)
		refresh = RefreshToken.for_user(user)
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

		response = self.client.post(
			'/api/revisions/submit-review/',
			{'problem_id': problem.id, 'confidence_rating': 4},
			format='json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(UserProblem.objects.get(user=user, problem=problem).solved)
		self.client.post(
			'/api/revisions/submit-review/',
			{'problem_id': problem.id, 'confidence_rating': 5},
			format='json',
		)
		self.assertEqual(len(self.client.get('/api/auth/profile/').json()['solved_problems']), 1)
		self.assertEqual(self.client.get('/api/dashboard/').json()['problems_solved'], 1)
		self.assertEqual(ReviewEvent.objects.filter(user=user, problem=problem).count(), 2)

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

	def test_dashboard_stats_returns_aggregated_metrics_and_grace_day_streaks(self):
		user = get_user_model().objects.create_user(username='stats-user')
		first_pattern = Pattern.objects.create(p_name='Arrays')
		second_pattern = Pattern.objects.create(p_name='Graphs')
		reviewed_problem = Problem.objects.create(
			title='Two Sum',
			leetcode_id=930001,
			link='https://leetcode.com/problems/two-sum/',
			difficulty='Easy',
			pattern=first_pattern,
		)
		pending_problem = Problem.objects.create(
			title='Number of Islands',
			leetcode_id=930002,
			link='https://leetcode.com/problems/number-of-islands/',
			difficulty='Medium',
			pattern=second_pattern,
		)
		now = timezone.now()
		today = timezone.localdate(now)
		UserProblemProgress.objects.create(
			user=user,
			problem=reviewed_problem,
			is_tracked=True,
			next_review_date=now + timedelta(days=10),
		)
		UserProblemProgress.objects.create(
			user=user,
			problem=pending_problem,
			is_tracked=True,
			next_review_date=now,
		)
		ReviewEvent.objects.create(
			user=user,
			problem=reviewed_problem,
			confidence=4,
			scheduled_for=now - timedelta(days=2),
			reviewed_at=now,
		)
		ReviewEvent.objects.create(
			user=user,
			problem=pending_problem,
			confidence=2,
			reviewed_at=now - timedelta(days=1),
		)
		ReviewEvent.objects.create(
			user=user,
			problem=reviewed_problem,
			confidence=3,
			reviewed_at=now - timedelta(days=3),
		)

		self.client.force_authenticate(user=user)
		response = self.client.get('/api/dashboard/stats/')
		payload = response.json()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['total_problems_tracked'], 2)
		self.assertEqual(payload['problems_due_today'], 1)
		self.assertEqual(payload['problems_due_this_week'], 1)
		self.assertEqual(payload['current_streak'], 3)
		self.assertEqual(payload['longest_streak'], 3)
		self.assertEqual(payload['revision_completion_7days'], 75)
		self.assertEqual(payload['total_reviews_done'], 3)
		self.assertEqual(payload['avg_confidence'], 3)
		self.assertEqual(payload['patterns_covered'], 2)
		self.assertEqual(payload['this_week_reviewed'], 3)
		self.assertEqual(payload['onboarding_status'], 'active')
		self.assertFalse(payload['has_leetcode_connected'])
		self.assertEqual(len(payload['activity_last_90days']), 90)
		self.assertEqual(payload['activity_last_90days'][-1]['date'], today.isoformat())

	def test_dashboard_stats_reports_empty_user_as_new_and_requires_authentication(self):
		response = self.client.get('/api/dashboard/stats/')
		self.assertEqual(response.status_code, 401)

		user = get_user_model().objects.create_user(username='new-stats-user')
		self.client.force_authenticate(user=user)
		response = self.client.get('/api/dashboard/stats/')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['onboarding_status'], 'new')
		self.assertEqual(response.json()['revision_completion_7days'], 0)
		self.assertIsNone(response.json()['avg_confidence'])
		self.assertEqual(response.json()['activity_last_90days'][-1]['count'], 0)

	def test_dashboard_uses_distinct_patterns_when_confidence_is_tied(self):
		user = get_user_model().objects.create_user(username='tie-user')
		pattern_names = ['Alpha Pattern', 'Zulu Pattern']
		for index, name in enumerate(pattern_names, start=1):
			pattern = Pattern.objects.create(p_name=name)
			problem = Problem.objects.create(
				title=f'Tied Pattern Problem {index}',
				leetcode_id=92000 + index,
				link=f'https://leetcode.com/problems/tied-pattern-{index}/',
				difficulty='Easy',
				pattern=pattern,
			)
			ReviewEvent.objects.create(user=user, problem=problem, confidence=4)

		self.client.force_authenticate(user=user)
		response = self.client.get('/api/dashboard/')

		self.assertEqual(response.status_code, 200)
		self.assertNotEqual(
			response.json()['strongest_pattern']['name'],
			response.json()['weakest_pattern']['name'],
		)


class AnalyticsTests(APITestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username='analytics-user')
		self.client.force_authenticate(user=self.user)
		self.pattern = Pattern.objects.create(p_name='Binary Search')
		self.unstarted_pattern = Pattern.objects.create(p_name='Graph Traversal')
		self.problem = Problem.objects.create(
			title='Search Insert Position',
			leetcode_id=35,
			link='https://leetcode.com/problems/search-insert-position/',
			difficulty='Easy',
			pattern=self.pattern,
		)
		self.second_problem = Problem.objects.create(
			title='Find First and Last Position',
			leetcode_id=34,
			link='https://leetcode.com/problems/find-first-and-last-position-of-element-in-sorted-array/',
			difficulty='Medium',
			pattern=self.pattern,
		)
		self.unstarted_problem = Problem.objects.create(
			title='Number of Islands',
			leetcode_id=200,
			link='https://leetcode.com/problems/number-of-islands/',
			difficulty='Medium',
			pattern=self.unstarted_pattern,
		)

	def test_analytics_endpoints_aggregate_user_data_and_recommend_actions(self):
		now = timezone.now()
		UserProblemProgress.objects.create(
			user=self.user,
			problem=self.problem,
			confidence_rating=2,
			next_review_date=now - timedelta(days=8),
		)
		UserProblemProgress.objects.create(
			user=self.user,
			problem=self.second_problem,
			confidence_rating=1,
			next_review_date=now + timedelta(days=2),
		)
		for days_ago, confidence in [(12, 5), (11, 4), (10, 4), (2, 2), (1, 1), (0, 1)]:
			ReviewEvent.objects.create(
				user=self.user,
				problem=self.problem,
				confidence=confidence,
				reviewed_at=now - timedelta(days=days_ago),
			)

		strength = self.client.get('/api/analytics/pattern-strength/')
		self.assertEqual(strength.status_code, 200)
		pattern_data = next(item for item in strength.json()['patterns'] if item['pattern_id'] == self.pattern.id)
		self.assertEqual(pattern_data['average_confidence'], 1.5)
		self.assertEqual(pattern_data['total_problems'], 2)
		self.assertEqual(pattern_data['trend'], 'declining')
		self.assertEqual(len(strength.json()['strongest']), 1)
		self.assertEqual(len(strength.json()['weakest']), 1)

		recommendations = self.client.get('/api/analytics/recommendations/')
		self.assertEqual(recommendations.status_code, 200)
		recommendation_types = {item['type'] for item in recommendations.json()}
		self.assertEqual(recommendation_types, {'weak_pattern', 'overdue', 'declining', 'not_started'})
		overdue_item = next(item for item in recommendations.json() if item['type'] == 'overdue')
		self.assertEqual(overdue_item['problem_ids'], [self.problem.id])
		not_started_item = next(
			item for item in recommendations.json()
			if item['type'] == 'not_started' and item['pattern_id'] == self.unstarted_pattern.id
		)
		self.assertEqual(not_started_item['problem_ids'], [self.unstarted_problem.id], recommendations.json())

		activity = self.client.get('/api/analytics/activity-heatmap/')
		self.assertEqual(activity.status_code, 200)
		self.assertEqual(len(activity.json()), 90)
		self.assertEqual(activity.json()[-1]['count'], 1)

		confidence = self.client.get('/api/analytics/confidence-trend/')
		self.assertEqual(confidence.status_code, 200)
		self.assertEqual(len(confidence.json()), 30)
		today = timezone.localdate()
		today_data = next(item for item in confidence.json() if item['date'] == today.isoformat())
		self.assertEqual(today_data['average_confidence'], 1)
		self.assertEqual(today_data['review_count'], 1)

	def test_analytics_endpoints_require_authentication(self):
		self.client.force_authenticate(user=None)
		for endpoint in (
			'/api/analytics/pattern-strength/',
			'/api/analytics/recommendations/',
			'/api/analytics/activity-heatmap/',
			'/api/analytics/confidence-trend/',
		):
			with self.subTest(endpoint=endpoint):
				self.assertEqual(self.client.get(endpoint).status_code, 401)


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


class AssessmentTests(APITestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username='assessment-user')
		self.client.force_authenticate(user=self.user)
		self.pattern = Pattern.objects.create(p_name='Arrays')
		self.problems = [
			Problem.objects.create(
				title=f'Assessment Problem {index}',
				leetcode_id=91000 + index,
				link=f'https://leetcode.com/problems/assessment-{index}/',
				difficulty='Easy',
				pattern=self.pattern,
			)
			for index in range(5)
		]

	def test_generation_prioritizes_very_overdue_before_weak_and_recent(self):
		now = timezone.now()
		for problem in self.problems:
			UserProblemProgress.objects.create(
				user=self.user,
				problem=problem,
				next_review_date=now + timedelta(days=2),
			)
		UserProblemProgress.objects.filter(
			user=self.user,
			problem=self.problems[0],
		).update(next_review_date=now - timedelta(days=4))
		UserProblemProgress.objects.filter(
			user=self.user,
			problem=self.problems[1],
		).update(confidence_rating=2)
		ReviewEvent.objects.create(user=self.user, problem=self.problems[1], confidence=2)
		UserProblemProgress.objects.filter(
			user=self.user,
			problem=self.problems[2],
		).update(last_reviewed_at=now - timedelta(hours=1))

		assessment = generate_weekly_assessment(self.user)
		selected_ids = list(assessment.problems.values_list('problem_id', flat=True))

		self.assertEqual(assessment.total_problems, 5)
		self.assertEqual(selected_ids[0], self.problems[0].id)
		self.assertEqual(selected_ids[1], self.problems[1].id)
		self.assertEqual(selected_ids[2], self.problems[2].id)
		self.assertEqual(generate_weekly_assessment(self.user).id, assessment.id)

	def test_assessment_lifecycle_scores_answers_and_feeds_sm2_once(self):
		assessment = Assessment.objects.create(
			user=self.user,
			time_limit_minutes=20,
			total_problems=2,
		)
		AssessmentProblem.objects.create(
			assessment=assessment,
			problem=self.problems[0],
		)
		AssessmentProblem.objects.create(
			assessment=assessment,
			problem=self.problems[1],
		)

		start_response = self.client.post(f'/api/assessments/{assessment.id}/start/')
		self.assertEqual(start_response.status_code, 200)
		self.assertEqual(start_response.json()['status'], 'in_progress')

		answer_response = self.client.post(
			f'/api/assessments/{assessment.id}/submit-answer/',
			{'problem_id': self.problems[0].id, 'status': 'solved'},
			format='json',
		)
		self.assertEqual(answer_response.status_code, 200)
		self.assertEqual(answer_response.json()['status'], 'solved')

		result = self.client.post(f'/api/assessments/{assessment.id}/complete/').json()
		self.assertEqual(result['status'], 'completed')
		self.assertEqual(result['score_percentage'], 50)
		self.assertEqual(result['problems'][1]['status'], 'missed')
		self.assertEqual(
			UserProblemProgress.objects.get(user=self.user, problem=self.problems[0]).confidence_rating,
			4,
		)
		self.assertEqual(
			UserProblemProgress.objects.get(user=self.user, problem=self.problems[1]).confidence_rating,
			1,
		)
		self.assertEqual(ReviewEvent.objects.filter(user=self.user).count(), 2)
		self.client.post(f'/api/assessments/{assessment.id}/complete/')
		self.assertEqual(ReviewEvent.objects.filter(user=self.user).count(), 2)

	def test_current_and_history_are_user_scoped(self):
		for problem in self.problems:
			UserProblemProgress.objects.create(user=self.user, problem=problem)
		current_response = self.client.get('/api/assessments/current/')
		self.assertEqual(current_response.status_code, 200)
		self.assertEqual(current_response.json()['total_problems'], 5)
		self.assertEqual(len(self.client.get('/api/assessments/history/').json()), 1)

		other_user = get_user_model().objects.create_user(username='another-assessment-user')
		self.client.force_authenticate(user=other_user)
		self.assertEqual(self.client.get('/api/assessments/history/').json(), [])

	def test_generate_assessments_command_is_repeatable(self):
		for problem in self.problems:
			UserProblemProgress.objects.create(user=self.user, problem=problem)
		call_command('generate_assessments', stdout=StringIO())
		call_command('generate_assessments', stdout=StringIO())
		self.assertEqual(Assessment.objects.filter(user=self.user).count(), 1)


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
		empty_sheet = DSASheet.objects.create(title='Empty sheet', slug='empty-sheet')
		list_response = self.client.get('/api/sheets/')
		self.assertEqual(list_response.status_code, 200)
		self.assertNotIn(empty_sheet.slug, [sheet['slug'] for sheet in list_response.json()])
		sheet_summary = next(sheet for sheet in list_response.json() if sheet['slug'] == 'blind-75-test')
		self.assertEqual(sheet_summary['title'], 'Blind 75')
		self.assertEqual(sheet_summary['progress'], {'tracked': 0, 'total': 2})

		detail_response = self.client.get('/api/sheets/blind-75-test/')
		self.assertEqual(detail_response.status_code, 200)
		self.assertEqual(len(detail_response.json()['categories']), 2)
		problem = detail_response.json()['categories'][0]['problems'][0]
		self.assertFalse(problem['is_tracked_by_user'])
		self.assertEqual(problem['order'], 1)
		self.assertEqual(self.client.get('/api/sheets/empty-sheet/').status_code, 404)

	def test_progress_annotations_are_scoped_to_the_authenticated_user(self):
		other_user = get_user_model().objects.create_user(username='other-sheet-user')
		UserProblemProgress.objects.create(user=self.user, problem=self.first_problem)
		UserProblemProgress.objects.create(user=other_user, problem=self.second_problem)

		sheet_summary = next(
			sheet for sheet in self.client.get('/api/sheets/').json()
			if sheet['slug'] == self.sheet.slug
		)
		self.assertEqual(sheet_summary['tracked_count'], 1)
		self.assertEqual(sheet_summary['progress'], {'tracked': 1, 'total': 2})

		detail = self.client.get(f'/api/sheets/{self.sheet.slug}/').json()
		tracked_status = {
			item['problem']['id']: item['is_tracked_by_user']
			for category in detail['categories']
			for item in category['problems']
		}
		self.assertTrue(tracked_status[self.first_problem.id])
		self.assertFalse(tracked_status[self.second_problem.id])

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
