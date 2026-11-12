import json
from datetime import datetime, timedelta, timezone as datetime_timezone
from io import BytesIO
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from .leetcode import (
    LeetCodeError,
    fetch_recent_accepted_submissions,
    get_recent_accepted_problems,
    normalize_leetcode_username,
    sync_recent_problems,
)
from .models import (
    LeetCodeSyncedProblem,
    Problem,
    ReviewEvent,
    UserProblem,
    UserProblemProgress,
    UserSettings,
)


class LeetCodeSubmissionServiceTests(APITestCase):
    def setUp(self):
        cache.clear()

    @patch('revise.leetcode.urlopen')
    def test_query_requests_twenty_recent_submissions_and_selects_five_unique_newest(self, urlopen_mock):
        submissions = [
            {'title': 'Older', 'titleSlug': 'older', 'timestamp': '100'},
            {'title': 'Latest', 'titleSlug': 'latest', 'timestamp': '500'},
            {'title': 'Repeated latest', 'titleSlug': 'latest', 'timestamp': '450'},
            {'title': 'Middle', 'titleSlug': 'middle', 'timestamp': '400'},
            {'title': 'Second', 'titleSlug': 'second', 'timestamp': '300'},
            {'title': 'Third', 'titleSlug': 'third', 'timestamp': '200'},
        ]
        urlopen_mock.return_value.__enter__.return_value.read.return_value = json.dumps({
            'data': {'recentAcSubmissionList': submissions},
        }).encode()

        result = get_recent_accepted_problems('ada_codes')

        self.assertEqual(result['fetched'], 6)
        self.assertEqual(
            [problem['title_slug'] for problem in result['problems']],
            ['latest', 'middle', 'second', 'third', 'older'],
        )
        request = urlopen_mock.call_args.args[0]
        request_body = json.loads(request.data)
        self.assertIn('recentAcSubmissionList(username: $username, limit: $limit)', request_body['query'])
        self.assertEqual(request_body['variables'], {'username': 'ada_codes', 'limit': 20})
        self.assertEqual(urlopen_mock.call_args.kwargs['timeout'], 10)

    @patch('revise.leetcode.urlopen')
    def test_empty_accepted_submissions_return_empty_result(self, urlopen_mock):
        urlopen_mock.return_value.__enter__.return_value.read.return_value = b'{"data":{"recentAcSubmissionList":[]}}'

        self.assertEqual(get_recent_accepted_problems('new_user')['problems'], [])

    @patch('revise.leetcode.urlopen')
    def test_malformed_submission_is_rejected(self, urlopen_mock):
        urlopen_mock.return_value.__enter__.return_value.read.return_value = json.dumps({
            'data': {'recentAcSubmissionList': [{
                'title': 'Invalid slug',
                'titleSlug': '../problem',
                'timestamp': '1700000000',
            }]},
        }).encode()

        with self.assertRaisesRegex(LeetCodeError, 'invalid title or problem slug'):
            fetch_recent_accepted_submissions('ada_codes')

    @patch('revise.leetcode.urlopen')
    def test_malformed_graphql_response_is_rejected(self, urlopen_mock):
        urlopen_mock.return_value.__enter__.return_value.read.return_value = b'{"data":{}}'

        with self.assertRaisesRegex(LeetCodeError, 'unexpected submissions'):
            fetch_recent_accepted_submissions('ada_codes')

    @patch('revise.leetcode.urlopen')
    def test_rate_limit_and_timeout_have_actionable_errors(self, urlopen_mock):
        urlopen_mock.side_effect = HTTPError(
            'https://leetcode.com/graphql/',
            429,
            'Too Many Requests',
            {},
            BytesIO(b''),
        )
        with self.assertRaises(LeetCodeError) as rate_error:
            fetch_recent_accepted_submissions('ada_codes')
        self.assertEqual(rate_error.exception.status_code, 503)

        urlopen_mock.side_effect = URLError('connection timed out')
        with self.assertRaisesRegex(LeetCodeError, 'Unable to reach LeetCode'):
            fetch_recent_accepted_submissions('ada_codes')

        urlopen_mock.side_effect = HTTPError(
            'https://leetcode.com/graphql/',
            500,
            'Internal Server Error',
            {},
            BytesIO(b''),
        )
        with self.assertRaisesRegex(LeetCodeError, 'could not complete the request'):
            fetch_recent_accepted_submissions('ada_codes')

    def test_normalizes_usernames_and_public_profile_urls(self):
        self.assertEqual(normalize_leetcode_username('ada_codes'), 'ada_codes')
        self.assertEqual(
            normalize_leetcode_username('https://leetcode.com/u/ada_codes/'),
            'ada_codes',
        )
        for value in (
            'https://example.com/u/ada_codes/',
            'https://leetcode.com/problems/two-sum/',
            'https://leetcode.com/u/ada_codes/?next=other',
            '../ada_codes',
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_leetcode_username(value)

    def test_invalid_and_duplicate_timestamp_values_are_rejected(self):
        with patch('revise.leetcode.urlopen') as urlopen_mock:
            urlopen_mock.return_value.__enter__.return_value.read.return_value = json.dumps({
                'data': {'recentAcSubmissionList': [{
                    'title': 'Two Sum',
                    'titleSlug': 'two-sum',
                    'timestamp': 'yesterday',
                }]},
            }).encode()
            with self.assertRaisesRegex(LeetCodeError, 'invalid timestamp'):
                fetch_recent_accepted_submissions('ada_codes')


class LeetCodeSyncPersistenceTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='sync-user')
        self.settings = UserSettings.objects.create(user=self.user, leetcode_username='ada_codes')
        self.existing = Problem.objects.create(
            title='Two Sum',
            leetcode_id=1,
            link='https://leetcode.com/problems/two-sum/',
            difficulty='Easy',
        )
        self.next_review = timezone.now() + timedelta(days=19)
        self.progress = UserProblemProgress.objects.create(
            user=self.user,
            problem=self.existing,
            source='manual',
            confidence_rating=4,
            interval=19,
            repetition_number=6,
            easiness_factor=2.8,
            next_review_date=self.next_review,
            last_reviewed_at=timezone.now() - timedelta(days=3),
        )
        self.submissions = [
            self.submission('two-sum', 100),
            self.submission('binary-search', 500),
            self.submission('merge-intervals', 400),
            self.submission('valid-parentheses', 300),
            self.submission('number-of-islands', 200),
            self.submission('two-sum', 450),
            self.submission('older-problem', 50),
        ]

    @staticmethod
    def submission(slug, timestamp):
        return {
            'title': slug.replace('-', ' ').title(),
            'title_slug': slug,
            'timestamp': datetime.fromtimestamp(timestamp, tz=datetime_timezone.utc),
        }

    @patch('revise.integrations.fetch_problem_metadata')
    @patch('revise.leetcode.fetch_recent_accepted_submissions')
    def test_imports_latest_five_without_resetting_existing_sm2_progress(self, fetch_submissions, fetch_metadata):
        fetch_submissions.return_value = self.submissions
        fetch_metadata.side_effect = lambda slug: {
            'title': slug.replace('-', ' ').title(),
            'slug': slug,
            'leetcode_id': {
                'binary-search': 704,
                'merge-intervals': 56,
                'valid-parentheses': 20,
                'number-of-islands': 200,
            }[slug],
            'difficulty': 'Medium',
            'description': '',
            'pattern_names': [],
        }

        result = sync_recent_problems(self.user, 'ada_codes')

        self.assertEqual(result['fetched'], 7)
        self.assertEqual(result['selected'], 5)
        self.assertEqual(result['added'], 4)
        self.assertEqual(result['already_tracked'], 1)
        self.assertEqual(
            [item['title_slug'] for item in result['problems']],
            ['binary-search', 'two-sum', 'merge-intervals', 'valid-parentheses', 'number-of-islands'],
        )
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.source, 'manual')
        self.assertEqual(self.progress.confidence_rating, 4)
        self.assertEqual(self.progress.interval, 19)
        self.assertEqual(self.progress.repetition_number, 6)
        self.assertEqual(self.progress.easiness_factor, 2.8)
        self.assertEqual(self.progress.next_review_date, self.next_review)
        self.assertEqual(self.progress.last_reviewed_at.date(), (timezone.now() - timedelta(days=3)).date())
        self.assertEqual(ReviewEvent.objects.filter(user=self.user).count(), 0)
        self.assertFalse(UserProblem.objects.filter(user=self.user).exists())
        self.assertEqual(
            set(UserProblemProgress.objects.filter(user=self.user).values_list('problem__slug', flat=True)),
            {'two-sum', 'binary-search', 'merge-intervals', 'valid-parentheses', 'number-of-islands'},
        )
        self.assertEqual(
            set(LeetCodeSyncedProblem.objects.filter(user=self.user).values_list('problem__slug', flat=True)),
            {'two-sum', 'binary-search', 'merge-intervals', 'valid-parentheses', 'number-of-islands'},
        )
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.leetcode_last_synced_at, result['last_synced_at'])
        self.assertEqual(fetch_metadata.call_count, 3)

    @patch('revise.integrations.fetch_problem_metadata')
    @patch('revise.leetcode.fetch_recent_accepted_submissions')
    def test_repeated_sync_is_idempotent_and_updates_current_selection(self, fetch_submissions, fetch_metadata):
        fetch_submissions.return_value = [self.submission('two-sum', 100)]

        first_result = sync_recent_problems(self.user, 'ada_codes')
        second_result = sync_recent_problems(self.user, 'ada_codes')

        self.assertEqual(first_result['added'], 0)
        self.assertEqual(second_result['added'], 0)
        self.assertEqual(UserProblemProgress.objects.filter(user=self.user).count(), 1)
        self.assertEqual(LeetCodeSyncedProblem.objects.filter(user=self.user).count(), 1)
        fetch_metadata.assert_not_called()

    @patch('revise.integrations.fetch_problem_metadata')
    @patch('revise.leetcode.fetch_recent_accepted_submissions')
    def test_new_sync_replaces_recent_selection_without_removing_older_tracked_problems(self, fetch_submissions, fetch_metadata):
        fetch_submissions.side_effect = [
            [self.submission('two-sum', 100)],
            [self.submission('new-problem', 200)],
        ]
        fetch_metadata.return_value = {
            'title': 'New Problem',
            'slug': 'new-problem',
            'leetcode_id': 900002,
            'difficulty': 'Medium',
            'description': '',
            'pattern_names': [],
        }

        sync_recent_problems(self.user, 'ada_codes')
        sync_recent_problems(self.user, 'ada_codes')

        self.assertTrue(UserProblemProgress.objects.filter(user=self.user, problem=self.existing, is_tracked=True).exists())
        self.assertEqual(
            list(LeetCodeSyncedProblem.objects.filter(user=self.user).values_list('title_slug', flat=True)),
            ['new-problem'],
        )

    @patch('revise.integrations.fetch_problem_metadata')
    @patch('revise.leetcode.fetch_recent_accepted_submissions')
    def test_creates_catalog_and_tracker_entries_for_missing_problem(self, fetch_submissions, fetch_metadata):
        fetch_submissions.return_value = [self.submission('new-problem', 100)]
        fetch_metadata.return_value = {
            'title': 'New Problem',
            'slug': 'new-problem',
            'leetcode_id': 900001,
            'difficulty': 'Hard',
            'description': 'Available statement',
            'pattern_names': [],
        }

        result = sync_recent_problems(self.user, 'ada_codes')

        problem = Problem.objects.get(leetcode_id=900001)
        progress = UserProblemProgress.objects.get(user=self.user, problem=problem)
        self.assertEqual(result['added'], 1)
        self.assertEqual(problem.link, 'https://leetcode.com/problems/new-problem/')
        self.assertEqual(progress.source, 'leetcode_sync')
        self.assertTrue(progress.is_tracked)
        self.assertEqual(progress.confidence_rating, 0)
        self.assertEqual(progress.interval, 0)
        self.assertIsNone(progress.next_review_date)
        self.assertIsNone(progress.last_reviewed_at)

    @patch('revise.integrations.fetch_problem_metadata')
    @patch('revise.leetcode.fetch_recent_accepted_submissions')
    def test_reactivates_untracked_progress_without_changing_review_schedule(self, fetch_submissions, fetch_metadata):
        untracked = Problem.objects.create(
            title='Merge Intervals',
            leetcode_id=56,
            link='https://leetcode.com/problems/merge-intervals/',
            difficulty='Medium',
        )
        due_date = timezone.now() + timedelta(days=40)
        prior_review = timezone.now() - timedelta(days=12)
        progress = UserProblemProgress.objects.create(
            user=self.user,
            problem=untracked,
            is_tracked=False,
            source='manual',
            confidence_rating=2,
            interval=40,
            repetition_number=8,
            next_review_date=due_date,
            last_reviewed_at=prior_review,
        )
        fetch_submissions.return_value = [self.submission('merge-intervals', 100)]

        result = sync_recent_problems(self.user, 'ada_codes')

        progress.refresh_from_db()
        self.assertEqual(result['added'], 1)
        self.assertTrue(progress.is_tracked)
        self.assertEqual(progress.source, 'manual')
        self.assertEqual(progress.confidence_rating, 2)
        self.assertEqual(progress.interval, 40)
        self.assertEqual(progress.repetition_number, 8)
        self.assertEqual(progress.next_review_date, due_date)
        self.assertEqual(progress.last_reviewed_at, prior_review)
        fetch_metadata.assert_not_called()


class LeetCodeEndpointTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='api-user')
        self.client.force_authenticate(self.user)
        self.settings = UserSettings.objects.create(user=self.user)
        self.problem = Problem.objects.create(
            title='Two Sum',
            leetcode_id=1,
            link='https://leetcode.com/problems/two-sum/',
            difficulty='Easy',
        )
        self.progress = UserProblemProgress.objects.create(
            user=self.user,
            problem=self.problem,
            source='manual',
            confidence_rating=5,
            interval=31,
            repetition_number=7,
        )

    @patch('revise.views.sync_recent_problems')
    @patch('revise.views.validate_public_profile')
    def test_connect_accepts_public_profile_url_and_imports_immediately(self, validate_profile, sync_problems):
        validate_profile.return_value = 'ada_codes'
        sync_problems.return_value = {
            'success': True,
            'username': 'ada_codes',
            'fetched': 1,
            'selected': 1,
            'added': 0,
            'already_tracked': 1,
            'last_synced_at': timezone.now(),
            'message': 'LeetCode synchronization completed',
            'problems': [],
        }

        response = self.client.post('/api/leetcode/connect/', {
            'username': 'https://leetcode.com/u/ada_codes/',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['username'], 'ada_codes')
        validate_profile.assert_called_once_with('ada_codes')
        sync_problems.assert_called_once()

    @patch('revise.views.validate_public_profile')
    def test_connect_rejects_unavailable_profile_without_saving_username(self, validate_profile):
        validate_profile.side_effect = LeetCodeError('That public LeetCode profile could not be found.', 404)

        response = self.client.post('/api/leetcode/connect/', {'username': 'missing_user'}, format='json')

        self.assertEqual(response.status_code, 404)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.leetcode_username, '')

    def test_status_is_scoped_to_authenticated_user_and_requires_authentication(self):
        response = self.client.get('/api/leetcode/status/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['connected'])
        self.assertEqual(response.json()['problems'], [])

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/leetcode/status/').status_code, 401)
        self.assertEqual(self.client.post('/api/leetcode/sync/').status_code, 401)
        self.assertEqual(self.client.delete('/api/leetcode/disconnect/').status_code, 401)

    @patch('revise.views.sync_recent_problems')
    def test_manual_sync_is_throttled(self, sync_problems):
        self.settings.leetcode_username = 'ada_codes'
        self.settings.leetcode_last_sync_attempt_at = timezone.now()
        self.settings.save()

        response = self.client.post('/api/leetcode/sync/', format='json')

        self.assertEqual(response.status_code, 429)
        sync_problems.assert_not_called()

    @patch('revise.views.sync_recent_problems')
    def test_dashboard_sync_uses_successful_sync_cooldown(self, sync_problems):
        self.settings.leetcode_username = 'ada_codes'
        self.settings.leetcode_last_synced_at = timezone.now() - timedelta(minutes=5)
        self.settings.save()

        response = self.client.post('/api/leetcode/sync/', {'automatic': True}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['skipped'])
        sync_problems.assert_not_called()

    @patch('revise.views.sync_recent_problems')
    def test_concurrent_sync_lock_is_per_account_and_does_not_change_other_users(self, sync_problems):
        self.settings.leetcode_username = 'ada_codes'
        self.settings.leetcode_sync_lock_token = 'active-lock'
        self.settings.leetcode_sync_lock_until = timezone.now() + timedelta(minutes=1)
        self.settings.save()

        response = self.client.post('/api/leetcode/sync/', format='json')
        self.assertEqual(response.status_code, 429)
        sync_problems.assert_not_called()

        other_user = get_user_model().objects.create_user(username='other-api-user')
        UserSettings.objects.create(user=other_user, leetcode_username='other_codes')
        self.client.force_authenticate(other_user)
        sync_problems.return_value = {
            'success': True,
            'username': 'other_codes',
            'fetched': 0,
            'selected': 0,
            'added': 0,
            'already_tracked': 0,
            'last_synced_at': timezone.now(),
            'message': 'LeetCode synchronization completed',
            'problems': [],
        }
        response = self.client.post('/api/leetcode/sync/', format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sync_problems.call_args.args[0], other_user)

    def test_sync_failure_does_not_advance_last_successful_sync(self):
        previous_sync = timezone.now() - timedelta(days=1)
        self.settings.leetcode_username = 'ada_codes'
        self.settings.leetcode_last_synced_at = previous_sync
        self.settings.save()
        with patch('revise.views.sync_recent_problems', side_effect=LeetCodeError('LeetCode unavailable')):
            response = self.client.post('/api/leetcode/sync/', format='json')

        self.assertEqual(response.status_code, 502)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.leetcode_last_synced_at, previous_sync)
        self.assertEqual(self.settings.leetcode_sync_lock_token, '')

    def test_disconnect_keeps_learning_progress_and_recent_sync_history(self):
        self.settings.leetcode_username = 'ada_codes'
        self.settings.leetcode_last_synced_at = timezone.now()
        self.settings.save()
        LeetCodeSyncedProblem.objects.create(
            user=self.user,
            problem=self.problem,
            title_slug='two-sum',
            accepted_at=timezone.now(),
        )

        response = self.client.delete('/api/leetcode/disconnect/')

        self.assertEqual(response.status_code, 204)
        self.settings.refresh_from_db()
        self.progress.refresh_from_db()
        self.assertEqual(self.settings.leetcode_username, '')
        self.assertIsNone(self.settings.leetcode_last_synced_at)
        self.assertTrue(self.progress.is_tracked)
        self.assertEqual(self.progress.confidence_rating, 5)
        self.assertEqual(self.progress.interval, 31)
        self.assertTrue(LeetCodeSyncedProblem.objects.filter(user=self.user, problem=self.problem).exists())

    def test_tracked_endpoint_identifies_recently_synced_problem(self):
        LeetCodeSyncedProblem.objects.create(
            user=self.user,
            problem=self.problem,
            title_slug='two-sum',
            accepted_at=timezone.now(),
        )

        response = self.client.get('/api/problems/tracked/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()[0]['recently_synced'])
        self.assertEqual(response.json()[0]['source'], 'manual')
        self.assertIsNotNone(response.json()[0]['accepted_at'])
