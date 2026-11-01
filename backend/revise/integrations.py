import json
from datetime import datetime, timezone as datetime_timezone
import re
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.cache import cache


LEETCODE_GRAPHQL_URL = 'https://leetcode.com/graphql/'
LEETCODE_SLUG_PATTERN = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


def parse_leetcode_url(url):
    """Return a LeetCode problem slug or reject non-problem URLs."""
    if not isinstance(url, str):
        raise ValueError('Enter a valid LeetCode problem URL.')

    try:
        parsed = urlparse(url.strip())
    except ValueError as error:
        raise ValueError('Enter a valid LeetCode problem URL.') from error

    if parsed.scheme not in ('http', 'https') or parsed.hostname not in ('leetcode.com', 'www.leetcode.com'):
        raise ValueError('Use a URL from leetcode.com.')

    path_parts = parsed.path.strip('/').split('/')
    if len(path_parts) != 2 or path_parts[0] != 'problems':
        raise ValueError('Use a LeetCode problem URL such as https://leetcode.com/problems/two-sum/.')

    slug = path_parts[1].lower()
    if not LEETCODE_SLUG_PATTERN.fullmatch(slug):
        raise ValueError('The LeetCode problem URL has an invalid problem slug.')
    return slug


def fetch_problem_metadata(slug):
    """Fetch public problem metadata from LeetCode and cache it briefly."""
    cache_key = f'recalldsa:leetcode:problem:{slug}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    request = Request(
        LEETCODE_GRAPHQL_URL,
        data=json.dumps({
            'query': (
                'query questionData($titleSlug: String!) { '
                'question(titleSlug: $titleSlug) { questionFrontendId title titleSlug '
                'difficulty content topicTags { name } } }'
            ),
            'variables': {'titleSlug': slug},
        }).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Referer': f'https://leetcode.com/problems/{slug}/',
            'User-Agent': 'RecallDSA/1.0',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError) as error:
        raise OSError('Unable to reach LeetCode. Please try again later.') from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('LeetCode returned an invalid response.') from error

    if not isinstance(payload, dict) or payload.get('errors'):
        raise ValueError('LeetCode could not load that problem.')

    data = payload.get('data')
    question = data.get('question') if isinstance(data, dict) else None
    if not isinstance(question, dict):
        raise LookupError('LeetCode could not find that problem.')

    try:
        leetcode_id = int(question['questionFrontendId'])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('LeetCode returned incomplete problem metadata.') from error

    difficulty = question.get('difficulty')
    if difficulty not in ('Easy', 'Medium', 'Hard') or not question.get('title'):
        raise ValueError('LeetCode returned incomplete problem metadata.')

    tags = question.get('topicTags') or []
    metadata = {
        'title': question['title'],
        'slug': question.get('titleSlug') or slug,
        'leetcode_id': leetcode_id,
        'difficulty': difficulty,
        'description': question.get('content') or '',
        'pattern_names': [
            tag['name'][:100]
            for tag in tags
            if isinstance(tag, dict) and isinstance(tag.get('name'), str) and tag['name'].strip()
        ],
    }
    cache.set(cache_key, metadata, timeout=300)
    return metadata


def fetch_recent_accepted_submissions(username):
    request = Request(
        LEETCODE_GRAPHQL_URL,
        data=json.dumps({
            'query': (
                'query recentAcSubmissions($username: String!) { '
                'recentAcSubmissionList(username: $username) { titleSlug timestamp } }'
            ),
            'variables': {'username': username},
        }).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'RecallDSA/1.0',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError) as error:
        raise OSError('Unable to reach LeetCode. Please try syncing again later.') from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('LeetCode returned an invalid response.') from error

    if not isinstance(payload, dict):
        raise ValueError('LeetCode returned an unexpected response.')
    if payload.get('errors'):
        raise ValueError('LeetCode could not find that username or rejected the sync request.')

    data = payload.get('data')
    submissions = data.get('recentAcSubmissionList') if isinstance(data, dict) else None
    if not isinstance(submissions, list):
        raise ValueError('LeetCode returned an unexpected submissions response.')

    result = []
    for submission in submissions:
        if not isinstance(submission, dict):
            continue
        title_slug = submission.get('titleSlug')
        timestamp = submission.get('timestamp')
        if not title_slug or not str(timestamp).isdigit():
            continue
        reviewed_at = datetime.fromtimestamp(
            int(timestamp),
            tz=datetime_timezone.utc,
        ).isoformat()
        result.append({'titleSlug': title_slug, 'timestamp': reviewed_at})
    return result
