#------------------------------------------------------------
#                      github_service.py
#               Handles GitHub API requests and
#                      response shaping.

import base64
import re
from typing import Dict, List, Tuple
import requests
from ..models import UpdateConfig

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
        headers = {"Accept": "application/vnd.github+json"}
        if self.config.github_token:
            headers["Authorization"] = f"Bearer {self.config.github_token}"
        return headers

    # This function does fetch accessible repositories from GitHub.
    # It pages through API results and returns a combined list.
    def fetch_repos(self) -> List[dict]:
        repos: List[dict] = []
        page = 1

        if self.config.github_token:
            base_url = "https://api.github.com/user/repos"
            print("Using authenticated /user/repos endpoint")
        else:
            base_url = f"https://api.github.com/users/{self.config.github_username}/repos"
            print("Using public-only /users/{username}/repos endpoint")

        while True:
            url = f"{base_url}?sort=pushed&direction=desc&per_page=100&page={page}"
            if not self.config.github_token:
                url += "&type=public"

            response = requests.get(url, headers=self.headers(), timeout=30)
            response.raise_for_status()
            data = response.json()
            if not data:
                break

            print(f"Page {page}: Found {len(data)} repositories")
            repos.extend(data)
            page += 1
            if page > 10:
                break

        return repos

    # This function does fetch and decode repository README text.
    # It strips non-content lines and returns condensed text.
    def fetch_readme_text(self, full_name: str) -> str:
        url = f"https://api.github.com/repos/{full_name}/readme"
        response = requests.get(url, headers=self.headers(), timeout=30)
        if response.status_code != 200:
            return ""

        data = response.json()
        content = data.get("content", "")
        encoding = data.get("encoding", "")
        if not content or encoding != "base64":
            return ""

        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        except Exception:
            return ""

        lines = []
        for line in decoded.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("#", "![", "[![", "<img", "<p align")):
                continue
            lines.append(stripped)
            if len(lines) >= 30:
                break

        return " ".join(lines)

    # This function does fetch language usage for a repository.
    # It caches results and falls back to the primary language.
    def fetch_language_usage(self, repo: dict) -> List[Tuple[str, int]]:
        repo_id = repo.get("id")
        if repo_id is None:
            primary = repo.get("language")
            return [(primary, 1)] if primary else []
        if repo_id in self.language_usage_cache:
            return self.language_usage_cache[repo_id]

        url = repo.get("languages_url")
        if not url:
            primary = repo.get("language")
            usage = [(primary, 1)] if primary else []
            self.language_usage_cache[repo_id] = usage
            return usage

        response = requests.get(url, headers=self.headers(), timeout=30)
        if response.status_code != 200:
            primary = repo.get("language")
            usage = [(primary, 1)] if primary else []
            self.language_usage_cache[repo_id] = usage
            return usage

        languages = response.json()
        if not isinstance(languages, dict) or not languages:
            primary = repo.get("language")
            usage = [(primary, 1)] if primary else []
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

        url = f"https://api.github.com/repos/{full_name}/contributors?per_page=1&anon=true"
        response = requests.get(url, headers=self.headers(), timeout=30)
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
        match = re.search(r"[?&]page=(\d+)>;\s*rel=\"last\"", link_header)
        if not match:
            return 0
        try:
            return int(match.group(1))
        except ValueError:
            return 0
