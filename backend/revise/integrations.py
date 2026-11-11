import json
from datetime import datetime, timezone as datetime_timezone
import hashlib
import html
import logging
import os
import re
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.cache import cache
from django.utils.html import strip_tags


LEETCODE_GRAPHQL_URL = 'https://leetcode.com/graphql/'
LEETCODE_SLUG_PATTERN = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
logger = logging.getLogger(__name__)


class RevisionSheetConfigurationError(Exception):
    pass


class RevisionSheetGenerationError(Exception):
    pass


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


def fetch_problem_metadata_by_id(leetcode_id):
    """Resolve a LeetCode frontend ID through the public problem list."""
    cache_key = f'recalldsa:leetcode:problem-id:{leetcode_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    request = Request(
        LEETCODE_GRAPHQL_URL,
        data=json.dumps({
            'query': (
                'query problemsetQuestionList($categorySlug: String, $limit: Int, '
                '$skip: Int, $filters: QuestionListFilterInput) { '
                'problemsetQuestionList: questionList(categorySlug: $categorySlug, '
                'limit: $limit, skip: $skip, filters: $filters) { '
                'questions: data { questionFrontendId titleSlug } } }'
            ),
            'variables': {
                'categorySlug': '',
                'limit': 50,
                'skip': 0,
                'filters': {'searchKeywords': str(leetcode_id)},
            },
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
        raise OSError('Unable to reach LeetCode. Please try again later.') from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('LeetCode returned an invalid response.') from error

    if not isinstance(payload, dict) or payload.get('errors'):
        raise ValueError('LeetCode could not search its problem list.')

    data = payload.get('data')
    result = data.get('problemsetQuestionList') if isinstance(data, dict) else None
    questions = result.get('questions') if isinstance(result, dict) else None
    if not isinstance(questions, list):
        raise ValueError('LeetCode returned an unexpected problem list.')

    question = next((
        item for item in questions
        if isinstance(item, dict)
        and str(item.get('questionFrontendId', '')).strip() == str(leetcode_id)
        and isinstance(item.get('titleSlug'), str)
    ), None)
    if question is None:
        raise LookupError(f'LeetCode problem #{leetcode_id} could not be found.')

    metadata = fetch_problem_metadata(question['titleSlug'])
    if metadata['leetcode_id'] != leetcode_id:
        raise ValueError('LeetCode returned a different problem number than requested.')
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


def generate_revision_sheet_content(problems):
    """Generate, validate, and cache content for each problem independently."""
    base_url = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
    model = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:1.5b')
    parsed_base_url = urlparse(base_url)
    if parsed_base_url.scheme not in ('http', 'https') or not parsed_base_url.netloc:
        raise RevisionSheetConfigurationError(
            'OLLAMA_BASE_URL must be a valid HTTP or HTTPS URL.'
        )

    normalized_problems = [
        {
            'id': problem['id'],
            'title': problem['title'],
            'leetcode_id': problem['leetcode_id'],
            'difficulty': problem['difficulty'],
            'description': ' '.join(html.unescape(strip_tags(problem['description'] or '')).split()),
        }
        for problem in problems
    ]
    generated_content = {}
    for problem in normalized_problems:
        cache_input = json.dumps(problem, sort_keys=True)
        cache_key = f'recalldsa:revision-sheet:{model}:{hashlib.sha256(cache_input.encode()).hexdigest()}'
        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            generated_content[problem['id']] = cached
            continue

        content = _generate_revision_sheet_problem(problem, base_url, model)
        cache.set(cache_key, content, timeout=60 * 60 * 24 * 30)
        generated_content[problem['id']] = content

    return [
        {
            'problem_id': problem['id'],
            **{key: value for key, value in problem.items() if key != 'id'},
            **generated_content[problem['id']],
        }
        for problem in normalized_problems
    ]


def _generate_revision_sheet_problem(problem, base_url, model):
    """Generate one problem per request to avoid truncating batched JSON output."""
    request = Request(
        f'{base_url}/api/chat',
        data=json.dumps({
            'model': model,
            'format': 'json',
            'stream': False,
            'options': {
                'temperature': 0.1,
                'num_ctx': 2048,
                'num_predict': 1024,
                'num_thread': 4,
            },
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        'You are a helpful coding assistant. Return valid JSON matching this exact structure: '
                        '{"problems": [{"problem_id": %s, "python_solution": "...", "explanation": "...", "test_cases": [{"input": "...", "expected_output": "..."}, {"input": "...", "expected_output": "..."}]}]} '
                        'Provide a complete Python solution, a short explanation sentence, and exactly two test cases. No markdown code blocks.'
                    ) % problem['id'],
                },
                {
                    'role': 'user',
                    'content': json.dumps({
                        'problem_id': problem['id'],
                        'title': problem['title'],
                        'leetcode_id': problem['leetcode_id'],
                        'difficulty': problem['difficulty'],
                        'description': problem['description'],
                    }),
                },
            ],
        }).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=300) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        try:
            error_payload = json.loads(error.read(4096).decode('utf-8'))
            error_detail = error_payload.get('error', '')
        except (UnicodeDecodeError, json.JSONDecodeError):
            error_detail = ''
        if not isinstance(error_detail, str):
            error_detail = ''
        error_detail = ' '.join(error_detail.split())[:300]
        logger.warning(
            'Ollama revision-sheet request failed with status %s: %s',
            error.code,
            error_detail or 'No error detail returned.',
        )
        if error.code == 404:
            raise RevisionSheetGenerationError(
                f'Ollama model "{model}" is not available. Run "ollama pull {model}" and try again.'
            ) from error
        if error_detail:
            raise RevisionSheetGenerationError(
                f'Ollama could not generate the revision sheet: {error_detail}'
            ) from error
        raise RevisionSheetGenerationError(
            f'Ollama could not generate the revision sheet (HTTP {error.code}).'
        ) from error
    except (URLError, TimeoutError) as error:
        logger.warning('Unable to reach the local Ollama server at %s.', base_url)
        raise RevisionSheetGenerationError(
            f'Unable to connect to Ollama at {base_url}. Start Ollama and try again.'
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.warning('Ollama returned an invalid revision-sheet response.')
        raise RevisionSheetGenerationError(
            'Ollama returned an invalid response. Please try again.'
        ) from error

    try:
        content = payload['message']['content'].strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[1]
            if content.endswith('```'):
                content = content.rsplit('```', 1)[0]
            content = content.strip()
        generated = json.loads(content)
        generated_problems = generated.get('problems')
        if not isinstance(generated_problems, list) and isinstance(generated, dict):
            generated_problems = [generated]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        done_reason = payload.get('done_reason', 'unknown')
        generated_tokens = payload.get('eval_count', 'unknown')
        logger.warning(
            'Ollama returned invalid JSON for problem %s (done_reason=%s, eval_count=%s).',
            problem['id'],
            done_reason,
            generated_tokens,
        )
        if done_reason == 'length':
            raise RevisionSheetGenerationError(
                'Ollama reached its output limit before finishing the solution. '
                'Try selecting one problem or shorten the problem description.'
            ) from error
        raise RevisionSheetGenerationError(
            'Ollama returned invalid JSON for this problem. Please try again.'
        ) from error

    if not isinstance(generated_problems, list) or len(generated_problems) != 1:
        raise RevisionSheetGenerationError(
            'Ollama did not generate content for this problem. Please try again.'
        )

    item = generated_problems[0]
    solution = item.get('python_solution') if isinstance(item, dict) else None
    explanation = item.get('explanation') if isinstance(item, dict) else None
    test_cases = item.get('test_cases') if isinstance(item, dict) else None
    if (
        not isinstance(item, dict)
        or item.get('problem_id') != problem['id']
        or not isinstance(solution, str)
        or not solution.strip()
        or not isinstance(explanation, str)
        or not explanation.strip()
        or not isinstance(test_cases, list)
        or len(test_cases) != 2
    ):
        raise RevisionSheetGenerationError('Ollama returned invalid problem content. Please try again.')
    if any(
        not isinstance(test_case, dict)
        or 'input' not in test_case
        or 'expected_output' not in test_case
        for test_case in test_cases
    ):
        raise RevisionSheetGenerationError('Ollama returned invalid test cases. Please try again.')

    normalized_test_cases = [
        {
            **test_case,
            'input': _format_revision_sheet_value(test_case['input']),
            'expected_output': _format_revision_sheet_value(test_case['expected_output']),
        }
        for test_case in test_cases
    ]
    return {
        'python_solution': solution.strip(),
        'explanation': explanation.strip(),
        'test_cases': normalized_test_cases,
    }


def _format_revision_sheet_value(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
