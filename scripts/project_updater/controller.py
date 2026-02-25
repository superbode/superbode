#------------------------------------------------------------
#                        controller.py
#           Coordinates repository processing and
#                  README section updates.

import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple
from .config import (
    CURRENT_PROJECTS_END_MARKER,
    CURRENT_PROJECTS_START_MARKER,
    DEFAULT_OWNER_TYPE,
    DEFAULT_GITHUB_USERNAME,
    DEFAULT_LANGUAGE_SUMMARY_TOP,
    DEFAULT_RECENT_DAYS,
    DEFAULT_USES_CAP,
    EMPTY_CURRENT_PROJECTS_MESSAGE,
    EMPTY_PAST_PROJECTS_MESSAGE,
    ENV_EXCLUDE_PRIVATE_REPOS,
    ENV_GITHUB_TOKEN,
    ENV_GITHUB_USERNAME,
    LANGUAGE_SUMMARY_END_MARKER,
    LANGUAGE_SUMMARY_START_MARKER,
    MIN_PROFILE_REPO_SIZE,
    NO_GITHUB_TOKEN_MESSAGE,
    OWNER_LABEL_ORGANIZATION_TEMPLATE,
    OWNER_LABEL_USER_TEMPLATE,
    OWNER_TYPE_ORGANIZATION,
    PAST_PROJECTS_END_MARKER,
    PAST_PROJECTS_START_MARKER,
    README_PATH,
    ROLE_COLLABORATOR,
    ROLE_OWNER,
    UNKNOWN_OWNER_LABEL,
    load_description_overrides,
    load_ignored_languages,
    load_ignored_repos,
)
from .models import RepoPresentation, UpdateConfig
from .services.description_service import clean_text, select_description, select_languages
from .services.github_service import GitHubService
from .services.readme_service import load_readme, replace_section, save_readme
from .views.markdown_view import render_language_summary, render_repo_section

# This function does build a display-ready repository object.
# It combines summary, language, contributor, and ownership metadata.
def _build_repo_presentation(
    repo: dict,
    github_service: GitHubService,
    overrides: Dict[str, str],
    uses_cap: int,
    username: str,
) -> RepoPresentation:
    readme_text = github_service.fetch_readme_text(repo["full_name"])
    context_text = clean_text(" ".join(part for part in [repo.get("description") or "", readme_text] if part))

    summary = select_description(repo, context_text, overrides)
    language_usage = github_service.fetch_language_usage(repo)
    languages = select_languages(language_usage, context_text, uses_cap)
    contributors = github_service.fetch_contributor_count(repo)

    owner = (repo.get("owner") or {}).get("login") or UNKNOWN_OWNER_LABEL
    owner_type = (repo.get("owner") or {}).get("type") or DEFAULT_OWNER_TYPE
    owner_label = (
        OWNER_LABEL_ORGANIZATION_TEMPLATE.format(owner=owner)
        if owner_type.lower() == OWNER_TYPE_ORGANIZATION
        else OWNER_LABEL_USER_TEMPLATE.format(owner=owner)
    )
    role = ROLE_OWNER if owner.lower() == username.lower() else ROLE_COLLABORATOR

    return RepoPresentation(
        name=repo["name"],
        url=repo["html_url"],
        summary=summary,
        languages=languages,
        contributors=contributors,
        owner_label=owner_label,
        role=role,
    )

# This function does aggregate language byte totals across repositories.
# It filters ignored languages and returns the top ranked entries.
def _aggregate_language_totals(
    repos: List[dict],
    github_service: GitHubService,
    ignored_languages: set,
    top_n: int,
) -> List[Tuple[str, int]]:
    totals: Dict[str, int] = {}
    for repo in repos:
        for language, byte_count in github_service.fetch_language_usage(repo):
            if not language:
                continue
            if language.strip().lower() in ignored_languages:
                continue
            totals[language] = totals.get(language, 0) + int(byte_count or 0)

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return ranked[:top_n]

# This function does execute the full update workflow end-to-end.
# It fetches repos, prepares sections, and writes the README output.
def run_update() -> None:
    config = UpdateConfig(
        github_username=os.environ.get(ENV_GITHUB_USERNAME, DEFAULT_GITHUB_USERNAME),
        github_token=os.environ.get(ENV_GITHUB_TOKEN, ""),
        recent_days=DEFAULT_RECENT_DAYS,
        uses_cap=DEFAULT_USES_CAP,
        language_summary_top=DEFAULT_LANGUAGE_SUMMARY_TOP,
    )

    overrides = load_description_overrides()
    ignored_repos = load_ignored_repos()
    ignored_languages = load_ignored_languages()
    excluded_private_repos = {
        item.strip().lower()
        for item in os.environ.get(ENV_EXCLUDE_PRIVATE_REPOS, "").split(",")
        if item.strip()
    }

    print(f"Fetching {'public and private' if config.github_token else 'public'} repos for {config.github_username} …")
    if overrides:
        print(f"Loaded description overrides: {len(overrides)}")
    if ignored_repos:
        print(f"Loaded ignored repos: {len(ignored_repos)}")
    if ignored_languages:
        print(f"Loaded ignored languages: {len(ignored_languages)}")
    if excluded_private_repos:
        print(f"Loaded excluded private repos: {len(excluded_private_repos)}")
    if not config.github_token:
        print(NO_GITHUB_TOKEN_MESSAGE)

    github_service = GitHubService(config)
    all_repos = github_service.fetch_repos()
    print(f"\nRaw API response: {len(all_repos)} repositories")

    filtered_repos = []
    for repo in all_repos:
        repo_name = (repo.get("name") or "").strip().lower()
        if repo.get("private") and repo_name in excluded_private_repos:
            print(f"Skipping excluded private repo: {repo.get('name')}")
            continue
        if repo_name in ignored_repos:
            print(f"Skipping ignored repo: {repo.get('name')}")
            continue

        if (
            repo["name"] == config.github_username
            and repo.get("stargazers_count", 0) == 0
            and repo.get("forks_count", 0) == 0
            and not (repo.get("description") or "").strip()
            and repo.get("size", 0) < MIN_PROFILE_REPO_SIZE
        ):
            print(f"Skipping minimal profile repo: {repo['name']}")
            continue

        filtered_repos.append(repo)

    print(f"After filtering: {len(filtered_repos)} repositories included")

    deduped = {}
    for repo in filtered_repos:
        key = (repo.get("name") or "").strip().lower()
        if not key:
            continue
        existing = deduped.get(key)
        if existing is None or repo.get("pushed_at", "") > existing.get("pushed_at", ""):
            deduped[key] = repo

    all_repos = list(deduped.values())
    all_repos.sort(key=lambda item: item["pushed_at"], reverse=True)
    print(f"After deduplication: {len(all_repos)} repositories included")

    cutoff = datetime.now(timezone.utc) - timedelta(days=config.recent_days)
    current_repos_raw = []
    past_repos_raw = []
    for repo in all_repos:
        pushed_date = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        if pushed_date >= cutoff:
            current_repos_raw.append(repo)
        else:
            past_repos_raw.append(repo)

    print(f"  Found {len(all_repos)} total repositories")
    print(f"  Current (updated within {config.recent_days} days): {len(current_repos_raw)} repos")
    print(f"  Past: {len(past_repos_raw)} repos")

    current_repos = [
        _build_repo_presentation(repo, github_service, overrides, config.uses_cap, config.github_username)
        for repo in current_repos_raw
    ]
    past_repos = [
        _build_repo_presentation(repo, github_service, overrides, config.uses_cap, config.github_username)
        for repo in past_repos_raw
    ]

    language_summary = render_language_summary(
        _aggregate_language_totals(all_repos, github_service, ignored_languages, config.language_summary_top)
    )

    readme = load_readme(README_PATH)
    readme = replace_section(readme, LANGUAGE_SUMMARY_START_MARKER, LANGUAGE_SUMMARY_END_MARKER, language_summary)
    readme = replace_section(
        readme,
        CURRENT_PROJECTS_START_MARKER,
        CURRENT_PROJECTS_END_MARKER,
        render_repo_section(current_repos, EMPTY_CURRENT_PROJECTS_MESSAGE),
    )
    readme = replace_section(
        readme,
        PAST_PROJECTS_START_MARKER,
        PAST_PROJECTS_END_MARKER,
        render_repo_section(past_repos, EMPTY_PAST_PROJECTS_MESSAGE),
    )

    save_readme(README_PATH, readme)
    print("README.md updated successfully.")
