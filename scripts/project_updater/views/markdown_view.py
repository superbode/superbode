#------------------------------------------------------------
#                      markdown_view.py
#                Renders markdown blocks for
#                projects and language stats.

from typing import List
from ..models import RepoPresentation

# This function does render one repository markdown block.
# It includes summary, languages, contributors, and ownership data.
def render_repo_block(repo: RepoPresentation) -> str:
    return (
        f"**[{repo.name}]({repo.url})** - {repo.summary}\n"
        f"- **Languages:** {repo.languages}\n"
        f"- **Contributors:** {repo.contributors}\n"
        f"- **Organization/Owner:** {repo.owner_label}\n"
        f"- **Role:** {repo.role}"
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
        return "_No language data available yet._"

    total_bytes = sum(count for _, count in language_totals)
    if total_bytes == 0:
        return "_No language data available yet._"

    lines = []
    for language, count in language_totals:
        percent = (count / total_bytes) * 100
        lines.append(f"- **{language}:** {percent:.1f}%")

    return "\n".join(lines)
