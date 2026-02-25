#------------------------------------------------------------
#                      github_service.py
#               Handles GitHub API requests and
#                      response shaping.

import base64
import re
from typing import Dict, List, Tuple
import requests
from ..config import (
    GITHUB_API_ACCEPT_HEADER,
    GITHUB_API_BASE_URL,
    GITHUB_CONTRIBUTOR_PER_PAGE,
    GITHUB_LANGUAGE_FALLBACK_BYTES,
    GITHUB_MAX_REPO_PAGES,
    GITHUB_README_MAX_LINES,
    GITHUB_REPOS_PER_PAGE,
    GITHUB_REQUEST_TIMEOUT_SECONDS,
)
from ..models import UpdateConfig

AUTH_REPOS_ENDPOINT = "/user/repos"
USER_REPOS_ENDPOINT_TEMPLATE = "/users/{username}/repos"
README_ENDPOINT_TEMPLATE = "/repos/{full_name}/readme"
CONTRIBUTORS_ENDPOINT_TEMPLATE = "/repos/{full_name}/contributors?per_page={per_page}&anon=true"
REPO_QUERY_TEMPLATE = "{base}?sort=pushed&direction=desc&per_page={per_page}&page={page}"
PUBLIC_REPOS_FILTER_QUERY = "&type=public"

AUTH_REPOS_MESSAGE = "Using authenticated /user/repos endpoint"
PUBLIC_REPOS_MESSAGE = "Using public-only /users/{username}/repos endpoint"
PAGE_RESULT_MESSAGE = "Page {page}: Found {count} repositories"

README_EXPECTED_ENCODING = "base64"
README_DECODE_ENCODING = "utf-8"
README_DECODE_ERROR_MODE = "ignore"
README_SKIP_PREFIXES = ("#", "![", "[![", "<img", "<p align")
LINK_LAST_PAGE_PATTERN = r"[?&]page=(\d+)>;\s*rel=\"last\""

class GitHubService:

    # This function does initialize service state and in-memory caches.
    # It stores runtime configuration used by API methods.
    def __init__(self, config: UpdateConfig):
        self.config = config
        self.contributor_count_cache: Dict[int, int] = {}
        self.language_usage_cache: Dict[int, List[Tuple[str, int]]] = {}

    # This function does build request headers for GitHub API calls.
    # It adds auth headers when a token is configured.
    def headers(self) -> Dict[str, str]:
        headers = {"Accept": GITHUB_API_ACCEPT_HEADER}
        if self.config.github_token:
            headers["Authorization"] = f"Bearer {self.config.github_token}"
        return headers

    # This function does fetch accessible repositories from GitHub.
    # It pages through API results and returns a combined list.
    def fetch_repos(self) -> List[dict]:
        repos: List[dict] = []
        page = 1

        if self.config.github_token:
            base_url = f"{GITHUB_API_BASE_URL}{AUTH_REPOS_ENDPOINT}"
            print(AUTH_REPOS_MESSAGE)
        else:
            base_url = f"{GITHUB_API_BASE_URL}{USER_REPOS_ENDPOINT_TEMPLATE.format(username=self.config.github_username)}"
            print(PUBLIC_REPOS_MESSAGE)

        while True:
            url = REPO_QUERY_TEMPLATE.format(base=base_url, per_page=GITHUB_REPOS_PER_PAGE, page=page)
            if not self.config.github_token:
                url += PUBLIC_REPOS_FILTER_QUERY

            response = requests.get(url, headers=self.headers(), timeout=GITHUB_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
            if not data:
                break

            print(PAGE_RESULT_MESSAGE.format(page=page, count=len(data)))
            repos.extend(data)
            page += 1
            if page > GITHUB_MAX_REPO_PAGES:
                break

        return repos

    # This function does fetch and decode repository README text.
    # It strips non-content lines and returns condensed text.
    def fetch_readme_text(self, full_name: str) -> str:
        url = f"{GITHUB_API_BASE_URL}{README_ENDPOINT_TEMPLATE.format(full_name=full_name)}"
        response = requests.get(url, headers=self.headers(), timeout=GITHUB_REQUEST_TIMEOUT_SECONDS)
        if response.status_code != 200:
            return ""

        data = response.json()
        content = data.get("content", "")
        encoding = data.get("encoding", "")
        if not content or encoding != README_EXPECTED_ENCODING:
            return ""

        try:
            decoded = base64.b64decode(content).decode(README_DECODE_ENCODING, errors=README_DECODE_ERROR_MODE)
        except Exception:
            return ""

        lines = []
        for line in decoded.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(README_SKIP_PREFIXES):
                continue
            lines.append(stripped)
            if len(lines) >= GITHUB_README_MAX_LINES:
                break

        return " ".join(lines)

    # This function does fetch language usage for a repository.
    # It caches results and falls back to the primary language.
    def fetch_language_usage(self, repo: dict) -> List[Tuple[str, int]]:
        repo_id = repo.get("id")
        if repo_id is None:
            primary = repo.get("language")
            return [(primary, GITHUB_LANGUAGE_FALLBACK_BYTES)] if primary else []
        if repo_id in self.language_usage_cache:
            return self.language_usage_cache[repo_id]

        url = repo.get("languages_url")
        if not url:
            primary = repo.get("language")
            usage = [(primary, GITHUB_LANGUAGE_FALLBACK_BYTES)] if primary else []
            self.language_usage_cache[repo_id] = usage
            return usage

        response = requests.get(url, headers=self.headers(), timeout=GITHUB_REQUEST_TIMEOUT_SECONDS)
        if response.status_code != 200:
            primary = repo.get("language")
            usage = [(primary, GITHUB_LANGUAGE_FALLBACK_BYTES)] if primary else []
            self.language_usage_cache[repo_id] = usage
            return usage

        languages = response.json()
        if not isinstance(languages, dict) or not languages:
            primary = repo.get("language")
            usage = [(primary, GITHUB_LANGUAGE_FALLBACK_BYTES)] if primary else []
            self.language_usage_cache[repo_id] = usage
            return usage

        usage = sorted(languages.items(), key=lambda item: item[1], reverse=True)
        self.language_usage_cache[repo_id] = usage
        return usage

    # This function does fetch contributor count for a repository.
    # It uses link headers when available and caches results.
    def fetch_contributor_count(self, repo: dict) -> int:
        repo_id = repo.get("id")
        if repo_id is None:
            return 0
        
        if repo_id in self.contributor_count_cache:
            return self.contributor_count_cache[repo_id]

        full_name = repo.get("full_name", "")
        if not full_name:
            return 0

        url = f"{GITHUB_API_BASE_URL}{CONTRIBUTORS_ENDPOINT_TEMPLATE.format(full_name=full_name, per_page=GITHUB_CONTRIBUTOR_PER_PAGE)}"
        response = requests.get(url, headers=self.headers(), timeout=GITHUB_REQUEST_TIMEOUT_SECONDS)
        if response.status_code != 200:
            self.contributor_count_cache[repo_id] = 0
            return 0

        last_page = self._parse_last_page_from_link_header(response.headers.get("Link", ""))
        if last_page > 0:
            self.contributor_count_cache[repo_id] = last_page
            return last_page

        try:
            data = response.json()
            count = len(data) if isinstance(data, list) else 0
        except Exception:
            count = 0

        self.contributor_count_cache[repo_id] = count
        return count

    # This function does parse the last page index from Link headers.
    # It returns zero when the header has no last-page reference.
    @staticmethod
    def _parse_last_page_from_link_header(link_header: str) -> int:
        if not link_header:
            return 0
        match = re.search(LINK_LAST_PAGE_PATTERN, link_header)
        if not match:
            return 0
        try:
            return int(match.group(1))
        except ValueError:
            return 0
