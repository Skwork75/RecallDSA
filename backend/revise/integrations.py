import json
from datetime import datetime, timezone as datetime_timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def fetch_recent_accepted_submissions(username):
    request = Request(
        'https://leetcode.com/graphql/',
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
