import requests

from tunga_tasks import slugs

EVENT_PUSH = 'push'
EVENT_CREATE = 'create'
EVENT_DELETE = 'delete'
EVENT_COMMIT_COMMENT = 'commit_comment'
EVENT_PULL_REQUEST = 'pull_request'
EVENT_PULL_REQUEST_REVIEW_COMMENT = 'pull_request_review_comment'
EVENT_ISSUE = 'issue'
EVENT_ISSUE_COMMENT = 'issue_comment'
EVENT_GOLLUM = 'gollum'
EVENT_RELEASE = 'release'

HEADER_EVENT_NAME = 'HTTP_X_GITHUB_EVENT'
HEADER_DELIVERY_ID = 'HTTP_X_GITHUB_DELIVERY'

PAYLOAD_ACTION = 'action'
PAYLOAD_ACTION_CREATED = 'created'
PAYLOAD_ACTION_DELETED = 'deleted'
PAYLOAD_ACTION_OPENED = 'opened'
PAYLOAD_ACTION_EDITED = 'edited'
PAYLOAD_ACTION_CLOSED = 'closed'
PAYLOAD_ACTION_REOPENED = 'reopened'
PAYLOAD_ACTION_PUBLISHED = 'published'

PAYLOAD_COMMENT = 'comment'
PAYLOAD_HTML_URL = 'html_url'
PAYLOAD_SENDER = 'sender'
PAYLOAD_USER = 'user'
PAYLOAD_USERNAME = 'login'
PAYLOAD_AVATAR_URL = 'avatar_url'
PAYLOAD_BODY = 'body'
PAYLOAD_CREATED_AT = 'created_at'

PAYLOAD_REF_TYPE = 'ref_type'
PAYLOAD_REF = 'ref'
PAYLOAD_REF_TYPE_REPO = 'repository'
PAYLOAD_REF_TYPE_BRANCH = 'branch'
PAYLOAD_REF_TYPE_TAG = 'tag'

PAYLOAD_REPOSITORY = 'repository'

PAYLOAD_PAGES = 'pages'
PAYLOAD_PAGE_NAME = 'page_name'
PAYLOAD_TITLE = 'title'
PAYLOAD_SUMMARY = 'summary'

PAYLOAD_HEAD_COMMIT = 'head_commit'
PAYLOAD_URL = 'url'
PAYLOAD_MESSAGE = 'message'
PAYLOAD_TIMESTAMP = 'timestamp'
PAYLOAD_ID = 'id'
PAYLOAD_TREE_ID = 'tree_id'

PAYLOAD_PULL_REQUEST = 'pull_request'
PAYLOAD_NUMBER = 'number'
PAYLOAD_MERGED = 'merged'
PAYLOAD_MERGED_AT = 'merged_at'

PAYLOAD_ISSUE = 'issue'
PAYLOAD_RELEASE = 'release'
PAYLOAD_TAG_NAME = 'tag_name'

REPOSITORY_FIELDS = ['id', 'name', 'description', 'full_name', 'private', 'url', 'html_url']

ISSUE_FIELDS = ['id', 'number', 'title', 'body', 'url', 'html_url', 'repository']


def transform_to_github_events(events):
    """
    Transforms Tunga integration events to corresponding GitHub events
    :param events: A list of Tunga events
    :return: A list of GitHub events
    """
    github_events = []
    event_map = {
        slugs.BRANCH: [EVENT_CREATE, EVENT_DELETE],
        slugs.TAG: [EVENT_CREATE, EVENT_DELETE],
        slugs.PULL_REQUEST_COMMENT: EVENT_PULL_REQUEST_REVIEW_COMMENT,
        slugs.WIKI: EVENT_GOLLUM,
    }
    if events:
        for tunga_event in events:
            if tunga_event in event_map:
                co_events = event_map[tunga_event]
                if isinstance(co_events, list):
                    github_events.extend(co_events)
                else:
                    github_events.append(co_events)
            else:
                github_events.append(tunga_event)
    return list(set(github_events))


def transform_to_tunga_event(event):
    event_map = {
        EVENT_CREATE: slugs.BRANCH,
        EVENT_DELETE: slugs.BRANCH,
        EVENT_PULL_REQUEST_REVIEW_COMMENT: slugs.PULL_REQUEST_COMMENT,
        EVENT_GOLLUM: slugs.WIKI,
    }
    return event_map.get(event, event)


def extract_repo_info(repo):
    repo_info = {}
    for key in REPOSITORY_FIELDS:
        repo_info[key] = repo[key]
    return repo_info


def api(endpoint, method, params=None, data=None, access_token=None):
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application.json'
    }
    if access_token:
        headers['Authorization'] = 'token %s' % access_token
    return requests.request(
            method=method, url='https://api.github.com'+endpoint, params=params, json=data, headers=headers
    )
