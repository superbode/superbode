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
import json
import base64
from datetime import datetime, timezone, timedelta

import requests
from dateutil import relativedelta

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "superbode")
EXCLUDE_PRIVATE_REPOS = set(os.environ.get("EXCLUDE_PRIVATE_REPOS", "").split(",")) if os.environ.get("EXCLUDE_PRIVATE_REPOS") else set()
README_PATH = os.path.join(os.path.dirname(__file__), "..", "README.md")
DESCRIPTION_OVERRIDES_PATH = os.path.join(
    os.path.dirname(__file__), "repo_description_overrides.json"
)
IGNORE_REPOS_PATH = os.path.join(
    os.path.dirname(__file__), "repo_ignore_list.json"
)
RECENT_DAYS = 30  # repos pushed within this many days are "current"
USES_CAP = 10
DESCRIPTION_OVERRIDES = {}
IGNORED_REPOS = set()
CONTRIBUTOR_COUNT_CACHE = {}


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


def load_description_overrides() -> dict:
    if not os.path.exists(DESCRIPTION_OVERRIDES_PATH):
        return {}

    try:
        with open(DESCRIPTION_OVERRIDES_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {}
        return {str(key).strip().lower(): str(value).strip() for key, value in data.items() if str(value).strip()}
    except Exception:
        return {}


def load_ignored_repos() -> set:
    if not os.path.exists(IGNORE_REPOS_PATH):
        return set()

    try:
        with open(IGNORE_REPOS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            return set()
        return {str(item).strip().lower() for item in data if str(item).strip()}
    except Exception:
        return set()


def split_sentences(text: str) -> list:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def clamp_sentence(sentence: str, max_words: int = 24) -> str:
    words = re.findall(r"[A-Za-z0-9+#.-]+", sentence)

    for size in range(6, 1, -1):
        if len(words) >= size * 2 and words[:size] == words[size:size * 2]:
            words = words[:size] + words[size * 2:]
            break

    if len(words) > max_words:
        words = words[:max_words]
    if not words:
        return ""
    clamped = " ".join(words)
    if not clamped.endswith("."):
        clamped += "."
    return clamped


def sentence_quality_score(sentence: str) -> int:
    lowered = sentence.lower()
    words = re.findall(r"[A-Za-z0-9+#.-]+", sentence)
    if len(words) < 7:
        return -100

    bad_patterns = [
        "installation",
        "contributing",
        "license",
        "make sure to sign in",
        "before starting this assignment",
        "assignment",
        "setup",
        "contributors list",
        "username",
        "please go through this link",
        "------------",
        "focuses on software engineering",
        "development workflows",
        "contains implementation details",
        "table of contents",
        "badge",
    ]
    if any(pattern in lowered for pattern in bad_patterns):
        return -50

    score = 0
    good_keywords = [
        "is",
        "builds",
        "provides",
        "implements",
        "allows",
        "application",
        "tool",
        "platform",
        "simulator",
        "game",
        "analy",
    ]
    for key in good_keywords:
        if key in lowered:
            score += 8

    score += max(0, 20 - abs(14 - len(words)))
    return score


def choose_best_sentence(*texts: str) -> str:
    candidates = []
    for text in texts:
        cleaned = clean_text(text)
        candidates.extend(split_sentences(cleaned))

    if not candidates:
        return ""

    ranked = sorted(candidates, key=sentence_quality_score, reverse=True)
    best = ranked[0]
    if sentence_quality_score(best) < 0:
        return ""
    return clamp_sentence(best)


def fallback_description(repo: dict) -> str:
    name = repo.get("name", "This repository")
    primary = repo.get("language") or "software"
    return f"{name} is a {primary} project with clear goals and practical implementation details."


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
        if len(lines) >= 30:
            break

    return " ".join(lines)


def fetch_language_usage(repo: dict) -> list:
    url = repo.get("languages_url")
    if not url:
        primary = repo.get("language")
        return [(primary, 1)] if primary else []

    response = requests.get(url, headers=github_headers(), timeout=30)
    if response.status_code != 200:
        primary = repo.get("language")
        return [(primary, 1)] if primary else []

    languages = response.json()
    if not isinstance(languages, dict) or not languages:
        primary = repo.get("language")
        return [(primary, 1)] if primary else []

    return sorted(languages.items(), key=lambda item: item[1], reverse=True)


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
        "microservice": "Microservices",
        "microservices": "Microservices",
        "mvc": "MVC",
        "rest": "REST API",
        "graphql": "GraphQL",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "azure": "Azure",
        "unity": "Unity",
        "shaderlab": "ShaderLab",
    }

    scores = {}
    lowered = (text or "").lower()
    for key, value in keywords.items():
        count = lowered.count(key)
        if count > 0:
            scores[value] = scores.get(value, 0) + count

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return ranked


def build_repo_context(repo: dict) -> str:
    readme_text = fetch_readme_text(repo["full_name"])
    base_text = " ".join(
        part for part in [repo.get("description") or "", readme_text] if part
    )
    return clean_text(base_text)


def repo_summary(repo: dict, context_text: str) -> str:
    override = DESCRIPTION_OVERRIDES.get((repo.get("name") or "").strip().lower())
    if override:
        return clamp_sentence(override)

    about = clean_text(repo.get("description") or "")
    if about and sentence_quality_score(about) >= 0:
        return clamp_sentence(about, max_words=18)

    best = choose_best_sentence(context_text)
    return best or fallback_description(repo)


def repo_uses(repo: dict, context_text: str) -> str:
    language_usage = fetch_language_usage(repo)
    framework_usage = infer_frameworks(context_text)

    merged = []
    seen = set()

    for language, _ in language_usage:
        if language and language not in seen:
            merged.append(language)
            seen.add(language)
        if len(merged) >= USES_CAP:
            break

    if len(merged) < USES_CAP:
        for framework, _ in framework_usage:
            if framework and framework not in seen:
                merged.append(framework)
                seen.add(framework)
            if len(merged) >= USES_CAP:
                break

    return ", ".join(merged) if merged else "Not specified"


def parse_last_page_from_link_header(link_header: str) -> int:
    if not link_header:
        return 0
    match = re.search(r"[?&]page=(\d+)>;\s*rel=\"last\"", link_header)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except ValueError:
        return 0


def fetch_contributor_count(repo: dict) -> int:
    repo_id = repo.get("id")
    if repo_id in CONTRIBUTOR_COUNT_CACHE:
        return CONTRIBUTOR_COUNT_CACHE[repo_id]

    full_name = repo.get("full_name", "")
    if not full_name:
        return 0

    url = f"https://api.github.com/repos/{full_name}/contributors?per_page=1&anon=true"
    response = requests.get(url, headers=github_headers(), timeout=30)
    if response.status_code != 200:
        CONTRIBUTOR_COUNT_CACHE[repo_id] = 0
        return 0

    last_page = parse_last_page_from_link_header(response.headers.get("Link", ""))
    if last_page > 0:
        CONTRIBUTOR_COUNT_CACHE[repo_id] = last_page
        return last_page

    try:
        data = response.json()
        count = len(data) if isinstance(data, list) else 0
    except Exception:
        count = 0

    CONTRIBUTOR_COUNT_CACHE[repo_id] = count
    return count


def repo_line(repo: dict) -> str:
    name = repo["name"]
    url = repo["html_url"]
    context_text = build_repo_context(repo)
    summary = repo_summary(repo, context_text)
    languages = repo_uses(repo, context_text)
    contributors = fetch_contributor_count(repo)

    owner = (repo.get("owner") or {}).get("login") or "Unknown"
    owner_type = (repo.get("owner") or {}).get("type") or "User"
    if owner_type.lower() == "organization":
        owner_label = f"Organization ({owner})"
    else:
        owner_label = f"Owner ({owner})"

    role = "Owner" if owner.lower() == GITHUB_USERNAME.lower() else "Contributor/Collaborator"
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)

    return (
        f"**[{name}]({url})** - {summary}\n"
        f"- **Languages:** {languages}\n"
        f"- **Contributors:** {contributors}\n"
        f"- **Organization/Owner:** {owner_label}\n"
        f"- **Role:** {role}\n"
        f"- **Stars/Forks:** {stars}/{forks}"
    )


def build_section(repos: list, empty_msg: str) -> str:
    if not repos:
        return empty_msg
    return "\n\n".join(repo_line(r) for r in repos)


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
    global DESCRIPTION_OVERRIDES, IGNORED_REPOS
    DESCRIPTION_OVERRIDES = load_description_overrides()
    IGNORED_REPOS = load_ignored_repos()

    repo_access = "public and private" if GITHUB_TOKEN else "public"
    print(f"Fetching {repo_access} repos for {GITHUB_USERNAME} …")
    if DESCRIPTION_OVERRIDES:
        print(f"Loaded description overrides: {len(DESCRIPTION_OVERRIDES)}")
    if IGNORED_REPOS:
        print(f"Loaded ignored repos: {len(IGNORED_REPOS)}")
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
        repo_name = (repo.get("name") or "").strip().lower()

        if repo_name in IGNORED_REPOS:
            print(f"Skipping ignored repo: {repo.get('name')}")
            continue

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
        name_key = (repo.get("name") or "").strip().lower()
        if not name_key:
            continue
        existing = unique_repos.get(name_key)
        if existing is None:
            unique_repos[name_key] = repo
            continue

        existing_pushed = existing.get("pushed_at", "")
        current_pushed = repo.get("pushed_at", "")
        if current_pushed > existing_pushed:
            unique_repos[name_key] = repo

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
