#------------------------------------------------------------
#                          models.py
#     Defines dataclasses used by the updater pipeline.

from dataclasses import dataclass
from typing import Dict, List
from .config import DEFAULT_LANGUAGE_SUMMARY_TOP, DEFAULT_RECENT_DAYS, DEFAULT_USES_CAP

@dataclass
class RepoPresentation:
    name: str
    url: str
    summary: str
    languages: str
    contributors: int
    owner_label: str
    role: str

@dataclass
class UpdateConfig:
    github_username: str
    github_token: str
    recent_days: int = DEFAULT_RECENT_DAYS
    uses_cap: int = DEFAULT_USES_CAP
    language_summary_top: int = DEFAULT_LANGUAGE_SUMMARY_TOP

@dataclass
class ResumeSnapshot:
    experiences: List[str]
    skills: Dict[str, List[str]]
