#------------------------------------------------------------
#                          config.py
#   Centralizes file paths and JSON config loading helpers.

import json
import os
from typing import Dict, Set

# Environment variable names for configuration
ENV_GITHUB_USERNAME = "GITHUB_USERNAME"
ENV_GITHUB_TOKEN = "GITHUB_TOKEN"
ENV_EXCLUDE_PRIVATE_REPOS = "EXCLUDE_PRIVATE_REPOS"
ENV_RESUME_PATH = "RESUME_PATH"

# Default values for configuration parameters
DEFAULT_GITHUB_USERNAME = "superbode"
DEFAULT_RECENT_DAYS = 30
DEFAULT_USES_CAP = 10
DEFAULT_LANGUAGE_SUMMARY_TOP = 10

# Constants for GitHub API interaction and README formatting
GITHUB_API_ACCEPT_HEADER = "application/vnd.github+json"
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_REPOS_PER_PAGE = 100
GITHUB_MAX_REPO_PAGES = 10
GITHUB_REQUEST_TIMEOUT_SECONDS = 30
GITHUB_README_MAX_LINES = 30
GITHUB_CONTRIBUTOR_PER_PAGE = 1
GITHUB_LANGUAGE_FALLBACK_BYTES = 1

# The minimum repository size (in KB) to consider.
MIN_PROFILE_REPO_SIZE = 50

# Markers used in README.md to identify sections for updates.
LANGUAGE_SUMMARY_START_MARKER = "<!-- LANGUAGE_SUMMARY:start -->"
LANGUAGE_SUMMARY_END_MARKER = "<!-- LANGUAGE_SUMMARY:end -->"
CURRENT_PROJECTS_START_MARKER = "<!-- CURRENT_PROJECTS:start -->"
CURRENT_PROJECTS_END_MARKER = "<!-- CURRENT_PROJECTS:end -->"
PAST_PROJECTS_START_MARKER = "<!-- PAST_PROJECTS:start -->"
PAST_PROJECTS_END_MARKER = "<!-- PAST_PROJECTS:end -->"
RESUME_EXPERIENCE_START_MARKER = "<!-- RESUME_EXPERIENCE:start -->"
RESUME_EXPERIENCE_END_MARKER = "<!-- RESUME_EXPERIENCE:end -->"
RESUME_SKILLS_START_MARKER = "<!-- RESUME_SKILLS:start -->"
RESUME_SKILLS_END_MARKER = "<!-- RESUME_SKILLS:end -->"

# Messages and templates for README content and logging.
EMPTY_CURRENT_PROJECTS_MESSAGE = "_No repositories updated within the last month._"
EMPTY_PAST_PROJECTS_MESSAGE = "_No repositories older than one month found._"
EMPTY_RESUME_EXPERIENCE_MESSAGE = "_No experience entries extracted from resume yet._"
EMPTY_RESUME_SKILLS_MESSAGE = "_No skill icons available yet._"

# Owner label templates for different GitHub owner types.
ROLE_OWNER = "Owner"
ROLE_COLLABORATOR = "Contributor/Collaborator"
OWNER_TYPE_ORGANIZATION = "organization"
DEFAULT_OWNER_TYPE = "User"
UNKNOWN_OWNER_LABEL = "Unknown"
OWNER_LABEL_ORGANIZATION_TEMPLATE = "Organization ({owner})"
OWNER_LABEL_USER_TEMPLATE = "Owner ({owner})"

# The message shown when no GITHUB_TOKEN is provided.
NO_GITHUB_TOKEN_MESSAGE = "No GITHUB_TOKEN found - only public repos will be shown"

# Directory paths for the project and configuration files.
SCRIPTS_DIR = os.path.dirname(os.path.dirname(__file__))
ROOT_DIR = os.path.dirname(SCRIPTS_DIR)
README_PATH = os.path.join(ROOT_DIR, "README.md")
CONFIG_DIR = os.path.join(SCRIPTS_DIR, "config")
DESCRIPTION_OVERRIDES_PATH = os.path.join(CONFIG_DIR, "repo_description_overrides.json")
IGNORE_REPOS_PATH = os.path.join(CONFIG_DIR, "repo_ignore_list.json")
IGNORE_LANGUAGES_PATH = os.path.join(CONFIG_DIR, "language_ignore_list.json")
DEFAULT_RESUME_FILENAME = "Bode Hooker Resume.pdf"

def resolve_resume_path() -> str:
    configured = os.environ.get(ENV_RESUME_PATH, "").strip()
    if configured:
        if os.path.isabs(configured):
            return configured
        return os.path.join(ROOT_DIR, configured)
    return os.path.join(ROOT_DIR, DEFAULT_RESUME_FILENAME)

# This function does load JSON content from disk safely.
# It returns None when the file is missing or invalid.
def _load_json(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except Exception:
        return None

# This function does load repository description overrides.
# It normalizes keys to lowercase for case-insensitive matching.
def load_description_overrides() -> Dict[str, str]:
    data = _load_json(DESCRIPTION_OVERRIDES_PATH)
    if not isinstance(data, dict):
        return {}
    return {
        str(key).strip().lower(): str(value).strip()
        for key, value in data.items()
        if str(value).strip()
    }

# This function does load the repository ignore list.
# It returns normalized lowercase names as a set.
def load_ignored_repos() -> Set[str]:
    data = _load_json(IGNORE_REPOS_PATH)
    if not isinstance(data, list):
        return set()
    return {str(item).strip().lower() for item in data if str(item).strip()}

# This function does load the language ignore list.
# It returns normalized lowercase language names as a set.
def load_ignored_languages() -> Set[str]:
    data = _load_json(IGNORE_LANGUAGES_PATH)
    if not isinstance(data, list):
        return set()
    return {str(item).strip().lower() for item in data if str(item).strip()}
