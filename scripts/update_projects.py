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
RECENT_DAYS = 120  # repos pushed within this many days are "current"
MAX_CURRENT = 20  # Show more current projects
MAX_PAST = 25     # Show more past projects


def github_headers():
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def fetch_repos():
    repos = []
    page = 1
    
    # Use /user/repos to get ALL repos the authenticated user has access to
    # This includes owned, collaborated, organization, and forked repos
    if GITHUB_TOKEN:
        # Authenticated endpoint - gets ALL accessible repos including private ones
        base_url = "https://api.github.com/user/repos"
        print("🔑 Using authenticated /user/repos endpoint")
    else:
        # Fallback to public repos only
        base_url = f"https://api.github.com/users/{GITHUB_USERNAME}/repos"
        print("⚠️  Using public-only /users/{username}/repos endpoint")
        
    while True:
        url = f"{base_url}?sort=pushed&direction=desc&per_page=100&page={page}"
        if not GITHUB_TOKEN:
            url += "&type=public"
        
        response = requests.get(url, headers=github_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        
        print(f"📄 Page {page}: Found {len(data)} repositories")
        
        # Only filter out explicitly excluded private repos
        filtered_repos = []
        for repo in data:
            # Skip excluded private repos only
            if repo["private"] and repo["name"] in EXCLUDE_PRIVATE_REPOS:
                print(f"⏭️  Skipping excluded private repo: {repo['name']}")
                continue
            # Include ALL other repos (owned, forks, collaborations, etc.)
            filtered_repos.append(repo)
        
        repos.extend(filtered_repos)
        page += 1
        
        # Safety limit to avoid infinite loops
        if page > 10:
            break
            
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
    is_fork = repo.get("fork", False)
    pushed_at = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    rel = relative_time(pushed_at)

    parts = [f"- **[{name}]({url})**"]
    
    if description:
        parts.append(f"– {description}")
        
    # Add indicators
    indicators = []
    if is_private:
        indicators.append("🔒")
    if is_fork:
        indicators.append("🍴")
    
    if indicators:
        parts.append(" ".join(indicators))
        
    parts.append(f"– `{language}`")
    
    if stars > 0:
        parts.append(f"⭐ {stars}")
    if forks > 0:
        parts.append(f"🔗 {forks}")
        
    parts.append(f"– _Updated {rel}_")
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
    if not GITHUB_TOKEN:
        print("⚠️  No GITHUB_TOKEN found - only public repos will be shown")
        print("   Set PERSONAL_ACCESS_TOKEN in repository secrets to include private repos")
    
    try:
        all_repos = fetch_repos()
    except requests.HTTPError as exc:
        print(f"ERROR fetching repos: {exc}", file=sys.stderr)
        if not GITHUB_TOKEN:
            print("TIP: Set GITHUB_TOKEN environment variable to access private repos", file=sys.stderr)
        sys.exit(1)
    
    # Debug: Show raw repo count before filtering
    print(f"\\n📊 Raw API response: {len(all_repos)} repositories")

    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)
    # Be much more inclusive - only exclude if explicitly excluded or truly minimal profile
    filtered_repos = []
    for repo in all_repos:
        # Only exclude profile repo if it's clearly just a minimal template
        if (repo["name"] == GITHUB_USERNAME and 
            repo.get("stargazers_count", 0) == 0 and 
            repo.get("forks_count", 0) == 0 and
            not (repo.get("description") or "").strip() and
            repo.get("size", 0) < 50):  # Very small indicates minimal content
            print(f"⏭️  Skipping minimal profile repo: {repo['name']}")
            continue
        filtered_repos.append(repo)
    
    print(f"📋 After filtering: {len(filtered_repos)} repositories included")
    all_repos = filtered_repos
    
    # Sort by most recent push date
    all_repos.sort(key=lambda r: r["pushed_at"], reverse=True)
    
    # Much more inclusive categorization - we want to show ALL repos
    current_repos = []
    past_repos = []
    
    for repo in all_repos:
        pushed_date = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        
        # Very inclusive criteria for "current" projects  
        is_current = (
            pushed_date > cutoff or  # Recent activity (120 days)
            repo.get("stargazers_count", 0) > 0 or  # Has stars
            repo.get("forks_count", 0) > 0 or  # Has forks  
            bool(repo.get("description", "").strip()) or  # Has description
            repo.get("private") == True or  # Include private repos as current
            repo.get("fork") == True  # Include forks as current (user has worked on them)
        )
        
        if is_current and len(current_repos) < MAX_CURRENT:
            current_repos.append(repo)
        elif len(past_repos) < MAX_PAST:
            past_repos.append(repo)
    
    print(f\"  Found {len(all_repos)} total repositories\")
            current_repos.append(repo)
        elif len(past_repos) < MAX_PAST:
            past_repos.append(repo)

    print(f"  Found {len(all_repos)} total repositories")
    print(f"  Current (recent or notable): {len(current_repos)} repos")
    print(f"  Past: {len(past_repos)} repos")
    
    # Debug: Show what repos were found
    if current_repos:
        print("\nCurrent repos:")
        for repo in current_repos:
            privacy = "🔒" if repo.get("private") else "🌍"
            print(f"  {privacy} {repo['name']} - {repo.get('language', 'N/A')} - Updated {relative_time(datetime.fromisoformat(repo['pushed_at'].replace('Z', '+00:00')))}")
    
    if past_repos:
        print("\nPast repos:")
        for repo in past_repos[:3]:  # Show first 3
            privacy = "🔒" if repo.get("private") else "🌍"
            print(f"  {privacy} {repo['name']} - {repo.get('language', 'N/A')} - Updated {relative_time(datetime.fromisoformat(repo['pushed_at'].replace('Z', '+00:00')))}")

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
