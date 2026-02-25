#------------------------------------------------------------
#                          models.py
#     Defines dataclasses used by the updater pipeline.

from dataclasses import dataclass

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
    recent_days: int = 30
    uses_cap: int = 10
    language_summary_top: int = 10
