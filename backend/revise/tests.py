from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Pattern, Problem, UserProblem


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
