#!/usr/bin/env python3
"""
Update the Current Projects and Past Projects sections of README.md
by querying the GitHub API for repositories (public and private with token) sorted by last push date.

Markers used in README.md:
  <!-- CURRENT_PROJECTS:start --> ... <!-- CURRENT_PROJECTS:end -->
  <!-- PAST_PROJECTS:start -->    ... <!-- PAST_PROJECTS:end -->

Environment variables:
  GITHUB_TOKEN: Personal access token with 'repo' scope for private repos
  GITHUB_USERNAME: GitHub username (default: superbode)
  EXCLUDE_PRIVATE_REPOS: Comma-separated list of private repo names to exclude
"""

import os
import re
import sys
from datetime import datetime, timezone, timedelta

import requests
from dateutil import relativedelta

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "superbode")
EXCLUDE_PRIVATE_REPOS = set(os.environ.get("EXCLUDE_PRIVATE_REPOS", "").split(",")) if os.environ.get("EXCLUDE_PRIVATE_REPOS") else set()
README_PATH = os.path.join(os.path.dirname(__file__), "..", "README.md")
RECENT_DAYS = 90  # repos pushed within this many days are "current" (increased from 21)
MAX_CURRENT = 6
MAX_PAST = 10


def github_headers():
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def fetch_repos():
    repos = []
    page = 1
    
    # Determine repo type based on token availability
    repo_type = "all" if GITHUB_TOKEN else "public"
    
    while True:
        url = (
            f"https://api.github.com/users/{GITHUB_USERNAME}/repos"
            f"?sort=pushed&direction=desc&per_page=100&page={page}&type={repo_type}"
        )
        response = requests.get(url, headers=github_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        
        # Filter out excluded private repos
        filtered_repos = []
        for repo in data:
            if repo["private"] and repo["name"] in EXCLUDE_PRIVATE_REPOS:
                continue  # Skip excluded private repos
            filtered_repos.append(repo)
        
        repos.extend(filtered_repos)
        page += 1
    return repos


def relative_time(dt: datetime) -> str:
    """Return a human-friendly relative time string."""
    now = datetime.now(timezone.utc)
    delta = relativedelta.relativedelta(now, dt)
    if delta.years > 0:
        return f"{delta.years} year{'s' if delta.years != 1 else ''} ago"
    if delta.months > 0:
        return f"{delta.months} month{'s' if delta.months != 1 else ''} ago"
    if delta.days > 0:
        return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
    hours = delta.hours
    if hours > 0:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    return "just now"


def repo_line(repo: dict) -> str:
    name = repo["name"]
    url = repo["html_url"]
    description = repo.get("description") or ""
    language = repo.get("language") or "N/A"
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    is_private = repo.get("private", False)
    pushed_at = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    rel = relative_time(pushed_at)

    parts = [f"- **[{name}]({url})**"]
    if description:
        parts.append(f"— {description}")
    if is_private:
        parts.append("🔒")
    parts.append(f"— `{language}`")
    if stars:
        parts.append(f"⭐ {stars}")
    if forks:
        parts.append(f"🍴 {forks}")
    parts.append(f"— _Updated {rel}_")
    return " ".join(parts)


def build_section(repos: list, empty_msg: str) -> str:
    if not repos:
        return empty_msg
    return "\n".join(repo_line(r) for r in repos)


def replace_section(content: str, start_marker: str, end_marker: str, new_body: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start_marker)})\n.*?({re.escape(end_marker)})",
        re.DOTALL,
    )
    replacement = rf"\1\n{new_body}\n\2"
    result, count = pattern.subn(replacement, content)
    if count == 0:
        print(f"WARNING: marker pair not found: {start_marker!r}", file=sys.stderr)
    return result


def main():
    repo_access = "public and private" if GITHUB_TOKEN else "public"
    print(f"Fetching {repo_access} repos for {GITHUB_USERNAME} …")
    if EXCLUDE_PRIVATE_REPOS:
        print(f"Excluding private repos: {', '.join(EXCLUDE_PRIVATE_REPOS)}")
    
    try:
        all_repos = fetch_repos()
    except requests.HTTPError as exc:
        print(f"ERROR fetching repos: {exc}", file=sys.stderr)
        if not GITHUB_TOKEN:
            print("TIP: Set GITHUB_TOKEN environment variable to access private repos", file=sys.stderr)
        sys.exit(1)

    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)
    # Exclude the profile README repo itself
    all_repos = [r for r in all_repos if r["name"] != GITHUB_USERNAME]
    
    # Include repos with recent activity OR interesting projects
    current_repos = []
    past_repos = []
    
    for repo in all_repos:
        pushed_date = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        
        # Check if repo is "current" (recent OR has meaningful activity)
        is_current = (
            pushed_date > cutoff or  # Recent activity
            repo.get("stargazers_count", 0) > 0 or  # Has stars
            repo.get("forks_count", 0) > 0 or  # Has forks  
            repo.get("description", "").strip()  # Has description
        )
        
        if is_current and len(current_repos) < MAX_CURRENT:
            current_repos.append(repo)
        elif len(past_repos) < MAX_PAST:
            past_repos.append(repo)

    print(f"  Current (last {RECENT_DAYS}d): {len(current_repos)} repos")
    print(f"  Past: {len(past_repos)} repos")

    with open(README_PATH, "r", encoding="utf-8") as fh:
        readme = fh.read()

    readme = replace_section(
        readme,
        "<!-- CURRENT_PROJECTS:start -->",
        "<!-- CURRENT_PROJECTS:end -->",
        build_section(
            current_repos,
            "_No recently active public repositories found — check back soon!_",
        ),
    )

    readme = replace_section(
        readme,
        "<!-- PAST_PROJECTS:start -->",
        "<!-- PAST_PROJECTS:end -->",
        build_section(past_repos, "_No past public repositories found yet._"),
    )

    with open(README_PATH, "w", encoding="utf-8") as fh:
        fh.write(readme)

    print("README.md updated successfully.")


if __name__ == "__main__":
    main()
