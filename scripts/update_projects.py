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
import base64
from datetime import datetime, timezone, timedelta

import requests
from dateutil import relativedelta

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "superbode")
EXCLUDE_PRIVATE_REPOS = set(os.environ.get("EXCLUDE_PRIVATE_REPOS", "").split(",")) if os.environ.get("EXCLUDE_PRIVATE_REPOS") else set()
README_PATH = os.path.join(os.path.dirname(__file__), "..", "README.md")
RECENT_DAYS = 30  # repos pushed within this many days are "current"


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
        print("Using authenticated /user/repos endpoint")
    else:
        # Fallback to public repos only
        base_url = f"https://api.github.com/users/{GITHUB_USERNAME}/repos"
        print("Using public-only /users/{username}/repos endpoint")
        
    while True:
        url = f"{base_url}?sort=pushed&direction=desc&per_page=100&page={page}"
        if not GITHUB_TOKEN:
            url += "&type=public"
        
        response = requests.get(url, headers=github_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        
        print(f"Page {page}: Found {len(data)} repositories")
        
        # Only filter out explicitly excluded private repos
        filtered_repos = []
        for repo in data:
            # Skip excluded private repos only
            if repo["private"] and repo["name"] in EXCLUDE_PRIVATE_REPOS:
                print(f"Skipping excluded private repo: {repo['name']}")
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


def clean_text(text: str) -> str:
    cleaned = text or ""
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"`+", "", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"^[#>*\-\s]+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def first_sentence(text: str) -> str:
    if not text:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
    return sentence


def normalize_description(repo_name: str, raw_text: str) -> str:
    default = (
        f"{repo_name} contains implementation details, project structure, and key development artifacts used recently."
    )
    source = first_sentence(clean_text(raw_text)) or default
    words = re.findall(r"[A-Za-z0-9+#.-]+", source)

    if len(words) > 15:
        words = words[:15]

    if len(words) < 10:
        filler = ["with", "clear", "project", "goals", "and", "organized", "code", "for", "practical", "use"]
        needed = 10 - len(words)
        words.extend(filler[:needed])

    sentence = " ".join(words).strip()
    if not sentence.endswith("."):
        sentence += "."
    return sentence


def fetch_readme_text(full_name: str) -> str:
    url = f"https://api.github.com/repos/{full_name}/readme"
    response = requests.get(url, headers=github_headers(), timeout=30)
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
        if len(lines) >= 4:
            break

    return " ".join(lines)


def fetch_languages(repo: dict) -> list:
    url = repo.get("languages_url")
    if not url:
        primary = repo.get("language")
        return [primary] if primary else []

    response = requests.get(url, headers=github_headers(), timeout=30)
    if response.status_code != 200:
        primary = repo.get("language")
        return [primary] if primary else []

    languages = response.json()
    if not isinstance(languages, dict) or not languages:
        primary = repo.get("language")
        return [primary] if primary else []

    top = sorted(languages.items(), key=lambda item: item[1], reverse=True)[:4]
    return [name for name, _ in top]


def infer_frameworks(text: str) -> list:
    keywords = {
        "react": "React",
        "next.js": "Next.js",
        "nextjs": "Next.js",
        "vue": "Vue",
        "angular": "Angular",
        "django": "Django",
        "flask": "Flask",
        "fastapi": "FastAPI",
        "spring": "Spring",
        "laravel": "Laravel",
        "express": "Express",
        "node": "Node.js",
        "unity": "Unity",
        "shaderlab": "ShaderLab",
    }

    found = []
    lowered = (text or "").lower()
    for key, value in keywords.items():
        if key in lowered and value not in found:
            found.append(value)
    return found


def repo_summary(repo: dict) -> str:
    readme_text = fetch_readme_text(repo["full_name"])
    base_text = readme_text or (repo.get("description") or "")
    return normalize_description(repo["name"], base_text)


def repo_uses(repo: dict, summary_text: str) -> str:
    languages = fetch_languages(repo)
    frameworks = infer_frameworks(summary_text)
    merged = []
    for item in languages + frameworks:
        if item and item not in merged:
            merged.append(item)
    return ", ".join(merged) if merged else "Not specified"


def repo_line(repo: dict) -> str:
    name = repo["name"]
    url = repo["html_url"]
    pushed_at = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    rel = relative_time(pushed_at)
    summary = repo_summary(repo)
    uses = repo_uses(repo, summary)
    return f"- [{name}]({url}) - {summary} - Uses: {uses} - Updated {rel}"


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
        print("No GITHUB_TOKEN found - only public repos will be shown")
        print("Set PERSONAL_ACCESS_TOKEN in repository secrets to include private repos")
    
    try:
        all_repos = fetch_repos()
    except requests.HTTPError as exc:
        print(f"ERROR fetching repos: {exc}", file=sys.stderr)
        if not GITHUB_TOKEN:
            print("TIP: Set GITHUB_TOKEN environment variable to access private repos", file=sys.stderr)
        sys.exit(1)
    
    # Debug: Show raw repo count before filtering
    print(f"\nRaw API response: {len(all_repos)} repositories")

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
            print(f"Skipping minimal profile repo: {repo['name']}")
            continue
        filtered_repos.append(repo)
    print(f"After filtering: {len(filtered_repos)} repositories included")

    unique_repos = {}
    for repo in filtered_repos:
        repo_id = repo.get("id")
        if repo_id is None:
            continue
        if repo_id not in unique_repos:
            unique_repos[repo_id] = repo

    all_repos = list(unique_repos.values())
    print(f"After deduplication: {len(all_repos)} repositories included")
    
    # Sort by most recent push date
    all_repos.sort(key=lambda r: r["pushed_at"], reverse=True)
    
    current_repos = []
    past_repos = []
    
    for repo in all_repos:
        pushed_date = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        
        if pushed_date >= cutoff:
            current_repos.append(repo)
        else:
            past_repos.append(repo)
    
    print(f"  Found {len(all_repos)} total repositories")
    print(f"  Current (updated within {RECENT_DAYS} days): {len(current_repos)} repos")
    print(f"  Past: {len(past_repos)} repos")
    
    # Debug: Show what repos were found
    if current_repos:
        print("\nCurrent repos:")
        for repo in current_repos:
            print(f"  {repo['name']} - {repo.get('language', 'N/A')} - Updated {relative_time(datetime.fromisoformat(repo['pushed_at'].replace('Z', '+00:00')))}")
    
    if past_repos:
        print("\nPast repos:")
        for repo in past_repos[:3]:  # Show first 3
            print(f"  {repo['name']} - {repo.get('language', 'N/A')} - Updated {relative_time(datetime.fromisoformat(repo['pushed_at'].replace('Z', '+00:00')))}")

    with open(README_PATH, "r", encoding="utf-8") as fh:
        readme = fh.read()

    readme = replace_section(
        readme,
        "<!-- CURRENT_PROJECTS:start -->",
        "<!-- CURRENT_PROJECTS:end -->",
        build_section(
            current_repos,
            "_No repositories updated within the last month._",
        ),
    )

    readme = replace_section(
        readme,
        "<!-- PAST_PROJECTS:start -->",
        "<!-- PAST_PROJECTS:end -->",
        build_section(past_repos, "_No repositories older than one month found._"),
    )

    with open(README_PATH, "w", encoding="utf-8") as fh:
        fh.write(readme)

    print("README.md updated successfully.")


if __name__ == "__main__":
    main()
