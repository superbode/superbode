#------------------------------------------------------------
#                          config.py
#   Centralizes file paths and JSON config loading helpers.

import json
import os
from typing import Dict, Set

SCRIPTS_DIR = os.path.dirname(os.path.dirname(__file__))
ROOT_DIR = os.path.dirname(SCRIPTS_DIR)
README_PATH = os.path.join(ROOT_DIR, "README.md")
CONFIG_DIR = os.path.join(SCRIPTS_DIR, "config")
DESCRIPTION_OVERRIDES_PATH = os.path.join(CONFIG_DIR, "repo_description_overrides.json")
IGNORE_REPOS_PATH = os.path.join(CONFIG_DIR, "repo_ignore_list.json")
IGNORE_LANGUAGES_PATH = os.path.join(CONFIG_DIR, "language_ignore_list.json")

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
