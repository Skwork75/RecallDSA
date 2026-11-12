import json
import re
from datetime import datetime, timezone as datetime_timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse


LEETCODE_GRAPHQL_URL = 'https://leetcode.com/graphql/'
LEETCODE_USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
LEETCODE_SLUG_PATTERN = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


class LeetCodeError(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def normalize_leetcode_username(value):
    if not isinstance(value, str):
        raise ValueError('Enter a LeetCode username or public profile URL.')

    value = value.strip()
    if '://' in value:
        try:
            profile = urlparse(value)
        except ValueError as error:
            raise ValueError('Enter a valid LeetCode profile URL.') from error
        if (
            profile.scheme not in ('http', 'https')
            or profile.hostname not in ('leetcode.com', 'www.leetcode.com')
            or profile.query
            or profile.fragment
        ):
            raise ValueError('Use a public LeetCode profile URL such as https://leetcode.com/u/username/.')
        parts = profile.path.strip('/').split('/')
        if len(parts) != 2 or parts[0] != 'u':
            raise ValueError('Use a public LeetCode profile URL such as https://leetcode.com/u/username/.')
        value = parts[1]

    if not LEETCODE_USERNAME_PATTERN.fullmatch(value):
        raise ValueError('Use a valid LeetCode username containing only letters, numbers, underscores, or hyphens.')
    return value


def _graphql_request(query, variables):
    request = Request(
        LEETCODE_GRAPHQL_URL,
        data=json.dumps({'query': query, 'variables': variables}).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Referer': 'https://leetcode.com/',
            'User-Agent': 'RecallDSA/1.0',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        if error.code == 429:
            raise LeetCodeError('LeetCode is rate limiting requests. Please try again later.', 503) from error
        raise LeetCodeError('LeetCode could not complete the request. Please try again later.') from error
    except (URLError, TimeoutError) as error:
        raise LeetCodeError('Unable to reach LeetCode. Please try again later.') from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LeetCodeError('LeetCode returned an invalid response.') from error

    if not isinstance(payload, dict):
        raise LeetCodeError('LeetCode returned an unexpected response.')
    if payload.get('errors'):
        raise LeetCodeError('LeetCode rejected the request. Its public API may have changed.')
    return payload


def validate_public_profile(username):
    payload = _graphql_request(
        'query publicProfile($username: String!) { matchedUser(username: $username) { username } }',
        {'username': username},
    )
    data = payload.get('data')
    matched_user = data.get('matchedUser') if isinstance(data, dict) else None
    canonical_username = matched_user.get('username') if isinstance(matched_user, dict) else None
    if not isinstance(data, dict) or 'matchedUser' not in data:
        raise LeetCodeError('LeetCode returned an unexpected public profile response.')
    if not isinstance(canonical_username, str) or not LEETCODE_USERNAME_PATTERN.fullmatch(canonical_username):
        raise LeetCodeError('That public LeetCode profile could not be found.', 404)
    return canonical_username


def fetch_recent_accepted_submissions(username, limit=20):
    request_limit = min(max(int(limit), 1), 20)
    payload = _graphql_request(
        'query recentAccepted($username: String!, $limit: Int!) { '
        'recentAcSubmissionList(username: $username, limit: $limit) { title titleSlug timestamp } }',
        {'username': username, 'limit': request_limit},
    )
    data = payload.get('data')
    submissions = data.get('recentAcSubmissionList') if isinstance(data, dict) else None
    if not isinstance(submissions, list):
        raise LeetCodeError('LeetCode returned an unexpected submissions response.')

    validated = []
    for submission in submissions:
        if not isinstance(submission, dict):
            raise LeetCodeError('LeetCode returned an invalid submission.')
        title = submission.get('title')
        title_slug = submission.get('titleSlug')
        timestamp = submission.get('timestamp')
        if (
            not isinstance(title, str)
            or not title.strip()
            or len(title.strip()) > 255
            or not isinstance(title_slug, str)
            or not LEETCODE_SLUG_PATTERN.fullmatch(title_slug)
        ):
            raise LeetCodeError('LeetCode returned a submission with an invalid title or problem slug.')
        if isinstance(timestamp, bool) or not (
            isinstance(timestamp, int) or isinstance(timestamp, str) and timestamp.isdigit()
        ):
            raise LeetCodeError('LeetCode returned a submission with an invalid timestamp.')
        try:
            timestamp_value = int(timestamp)
            if timestamp_value <= 0:
                raise ValueError('Timestamp must be positive.')
            accepted_at = datetime.fromtimestamp(timestamp_value, tz=datetime_timezone.utc)
        except (OverflowError, OSError, ValueError) as error:
            raise LeetCodeError('LeetCode returned a submission with an invalid timestamp.') from error
        validated.append({
            'title': title.strip(),
            'title_slug': title_slug,
            'timestamp': accepted_at,
        })
    return validated


def get_recent_accepted_problems(username, limit=5):
    limit = min(max(int(limit), 1), 5)
    submissions = fetch_recent_accepted_submissions(username, limit=20)
    submissions.sort(key=lambda item: item['timestamp'], reverse=True)
    selected = []
    seen_slugs = set()
    for submission in submissions:
        if submission['title_slug'] in seen_slugs:
            continue
        seen_slugs.add(submission['title_slug'])
        selected.append(submission)
        if len(selected) == limit:
            break
    return {'fetched': len(submissions), 'problems': selected}


def sync_recent_problems(user, username, lock_token=None):
    from django.db import transaction
    from django.db.models import Q
    from django.utils import timezone

    from .integrations import fetch_problem_metadata
    from .models import (
        LeetCodeSyncedProblem,
        Pattern,
        Problem,
        UserProblemProgress,
        UserSettings,
    )
    from .services import generate_milestone_assessments

    result = get_recent_accepted_problems(username)
    prepared = []
    for submission in result['problems']:
        slug = submission['title_slug']
        link = f'https://leetcode.com/problems/{slug}/'
        problem = Problem.objects.filter(Q(slug=slug) | Q(link__iexact=link)).first()
        metadata = None
        if problem is None:
            try:
                metadata = fetch_problem_metadata(slug)
            except (LookupError, OSError, ValueError) as error:
                raise LeetCodeError(
                    f'Could not load metadata for LeetCode problem "{submission["title"]}".'
                ) from error
            if (
                not isinstance(metadata, dict)
                or not isinstance(metadata.get('title'), str)
                or not metadata['title'].strip()
                or len(metadata['title'].strip()) > 255
                or type(metadata.get('leetcode_id')) is not int
                or metadata['leetcode_id'] < 1
                or metadata.get('difficulty') not in ('Easy', 'Medium', 'Hard')
                or metadata.get('slug') != slug
                or not isinstance(metadata.get('pattern_names', []), list)
                or any(
                    not isinstance(name, str) or not name.strip()
                    for name in metadata.get('pattern_names', [])
                )
                or not isinstance(metadata.get('description', ''), str)
            ):
                raise LeetCodeError('LeetCode returned incomplete problem metadata.')
        prepared.append((submission, problem, metadata, link))

    now = timezone.now()
    imported_count = 0
    problem_responses = []
    with transaction.atomic():
        settings_record = UserSettings.objects.select_for_update().get(user=user)
        if (
            settings_record.leetcode_username != username
            or lock_token and settings_record.leetcode_sync_lock_token != lock_token
        ):
            raise LeetCodeError('The connected LeetCode account changed during synchronization.', 409)

        for submission, problem, metadata, link in prepared:
            if problem is None:
                pattern_names = list(dict.fromkeys(
                    name.strip()[:100]
                    for name in metadata.get('pattern_names', [])
                    if isinstance(name, str) and name.strip()
                ))
                primary_pattern = None
                if pattern_names:
                    primary_pattern, _ = Pattern.objects.get_or_create(p_name=pattern_names[0])
                problem, _ = Problem.objects.get_or_create(
                    leetcode_id=metadata['leetcode_id'],
                    defaults={
                        'title': metadata['title'].strip()[:255],
                        'slug': submission['title_slug'],
                        'link': link,
                        'difficulty': metadata['difficulty'],
                        'description': metadata.get('description') or '',
                        'pattern': primary_pattern,
                    },
                )
                if problem.pattern_id is None and primary_pattern is not None:
                    problem.pattern = primary_pattern
                    problem.save(update_fields=['pattern'])
                for pattern_name in pattern_names:
                    pattern, _ = Pattern.objects.get_or_create(p_name=pattern_name)
                    problem.patterns.add(pattern)

            progress, created = UserProblemProgress.objects.get_or_create(
                user=user,
                problem=problem,
                defaults={
                    'is_tracked': True,
                    'source': 'leetcode_sync',
                },
            )
            already_tracked = not created and progress.is_tracked
            if not created and not progress.is_tracked:
                progress.is_tracked = True
                progress.save(update_fields=['is_tracked', 'updated_at'])
            if not already_tracked:
                imported_count += 1

            problem_responses.append({
                'id': problem.id,
                'title': problem.title,
                'title_slug': submission['title_slug'],
                'url': link,
                'difficulty': problem.difficulty,
                'already_tracked': already_tracked,
                'accepted_at': submission['timestamp'],
            })

        LeetCodeSyncedProblem.objects.filter(user=user).delete()
        LeetCodeSyncedProblem.objects.bulk_create([
            LeetCodeSyncedProblem(
                user=user,
                problem_id=problem_response['id'],
                title_slug=problem_response['title_slug'],
                accepted_at=problem_response['accepted_at'],
                synced_at=now,
            )
            for problem_response in problem_responses
        ])
        if imported_count:
            generate_milestone_assessments(user)
        settings_record.leetcode_last_synced_at = now
        settings_record.save(update_fields=['leetcode_last_synced_at'])

    return {
        'success': True,
        'username': username,
        'fetched': result['fetched'],
        'selected': len(problem_responses),
        'added': imported_count,
        'already_tracked': len(problem_responses) - imported_count,
        'last_synced_at': now,
        'message': 'LeetCode synchronization completed',
        'problems': problem_responses,
    }
