#------------------------------------------------------------
#                      markdown_view.py
#                Renders markdown blocks for
#                projects and language stats.

from typing import List
from ..models import RepoPresentation

NO_LANGUAGE_DATA_MESSAGE = "_No language data available yet._"
REPO_BLOCK_TEMPLATE = (
    "**[{name}]({url})** - {summary}\n"
    "- **Languages:** {languages}\n"
    "- **Contributors:** {contributors}\n"
    "- **Organization/Owner:** {owner_label}\n"
    "- **Role:** {role}"
)
LANGUAGE_LINE_TEMPLATE = "- **{language}:** {percent:.1f}%"

# This function does render one repository markdown block.
# It includes summary, languages, contributors, and ownership data.
def render_repo_block(repo: RepoPresentation) -> str:
    return REPO_BLOCK_TEMPLATE.format(
        name=repo.name,
        url=repo.url,
        summary=repo.summary,
        languages=repo.languages,
        contributors=repo.contributors,
        owner_label=repo.owner_label,
        role=repo.role,
    )

# This function does render a full project section block.
# It joins repository blocks or returns an empty-state message.
def render_repo_section(repos: List[RepoPresentation], empty_message: str) -> str:
    if not repos:
        return empty_message
    return "\n\n".join(render_repo_block(repo) for repo in repos)

# This function does render language percentage summary markdown.
# It computes percentages and formats bullet output lines.
def render_language_summary(language_totals: List[tuple]) -> str:
    if not language_totals:
        return NO_LANGUAGE_DATA_MESSAGE

    total_bytes = sum(count for _, count in language_totals)
    if total_bytes == 0:
        return NO_LANGUAGE_DATA_MESSAGE

    lines = []
    for language, count in language_totals:
        percent = (count / total_bytes) * 100
        lines.append(LANGUAGE_LINE_TEMPLATE.format(language=language, percent=percent))

    return "\n".join(lines)
