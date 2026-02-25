#------------------------------------------------------------
#                      markdown_view.py
#                Renders markdown blocks for
#                projects and language stats.

from typing import List
from ..models import RepoPresentation, ResumeExperienceEntry

NO_LANGUAGE_DATA_MESSAGE = "_No language data available yet._"
REPO_BLOCK_TEMPLATE = (
    "**[{name}]({url})** - {summary}\n"
    "- **Languages:** {languages}\n"
    "- **Contributors:** {contributors}\n"
    "- **Organization/Owner:** {owner_label}\n"
    "- **Role:** {role}"
)
LANGUAGE_LINE_TEMPLATE = "- **{language}:** {percent:.1f}%"
RESUME_EXPERIENCE_TITLE_TEMPLATE = "### {title}"
RESUME_EXPERIENCE_ROLE_TEMPLATE = "**{role}**"
RESUME_EXPERIENCE_DATE_TEMPLATE = "*{date_range}*"
RESUME_EXPERIENCE_LINE_TEMPLATE = "- {line}"

LANGUAGE_ICON_MAP = {
    "c#": "cs",
    "c++": "cpp",
    "c": "c",
    "java": "java",
    "python": "python",
    "html": "html",
    "css": "css",
    "javascript": "js",
    "typescript": "ts",
    "php": "php",
    "go": "go",
    "rust": "rust",
    "kotlin": "kotlin",
    "swift": "swift",
    "ruby": "ruby",
    "scala": "scala",
    "dart": "dart",
}

TOOL_PLATFORM_ICON_MAP = {
    "visual studio": "visualstudio",
    "vs": "visualstudio",
    "vs code": "vscode",
    "vscode": "vscode",
    "intellij idea": "idea",
    "intellij": "idea",
    "pycharm": "pycharm",
    "git": "git",
    "github": "github",
    "azure": "azure",
    "azure devops": "azure",
    "jira": "jira",
    "trello": "trello",
    "figma": "figma",
    "docker": "docker",
    "postman": "postman",
}

ICON_SECTION_TITLE_TEMPLATE = '<p align="center"><strong>{title}</strong></p>'
ICON_IMAGE_TEMPLATE = (
    '<p align="center">\n'
    '  <img src="https://skillicons.dev/icons?i={icons}&theme=dark" alt="{alt}" />\n'
    '</p>'
)
OTHER_TOOLS_LINE_TEMPLATE = "- {tool}"

def _split_experience_title(title_line: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in (title_line or "").split(" — ") if part.strip()]
    if len(parts) >= 3:
        company_and_location = parts[0]
        role = parts[1]
        date_range = " — ".join(parts[2:])
        return company_and_location, role, date_range
    if len(parts) == 2:
        return parts[0], parts[1], ""
    if len(parts) == 1:
        return parts[0], "", ""
    return "", "", ""

def _dedupe_keep_order(items: List[str]) -> List[str]:
    deduped = []
    seen = set()
    for item in items:
        normalized = (item or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped

def _render_icon_row(title: str, icon_ids: List[str], alt: str) -> str:
    if not icon_ids:
        return ""
    return "\n".join(
        [
            ICON_SECTION_TITLE_TEMPLATE.format(title=title),
            ICON_IMAGE_TEMPLATE.format(icons=",".join(icon_ids), alt=alt),
        ]
    )

def _collect_tools_platform_icons_and_other(skills: dict) -> tuple[List[str], List[str]]:
    tools_platform_sources = []
    for category in ("Tools", "Platforms", "Frameworks"):
        tools_platform_sources.extend(skills.get(category, []))

    icon_ids = []
    others = []
    for item in _dedupe_keep_order(tools_platform_sources):
        icon_id = TOOL_PLATFORM_ICON_MAP.get((item or "").strip().lower())
        if icon_id:
            icon_ids.append(icon_id)
        else:
            others.append(item)

    return _dedupe_keep_order(icon_ids), others

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

# This function does render extracted resume experience lines.
# It emits bullet points or an empty-state message.
def render_resume_experience(experiences: List[ResumeExperienceEntry], empty_message: str) -> str:
    if not experiences:
        return empty_message

    blocks = []
    for experience in experiences:
        company_and_location, role, date_range = _split_experience_title(experience.title_line)
        heading_title = company_and_location or experience.title_line
        lines = [RESUME_EXPERIENCE_TITLE_TEMPLATE.format(title=heading_title)]
        if role:
            lines.append(RESUME_EXPERIENCE_ROLE_TEMPLATE.format(role=role))
        if date_range:
            lines.append(RESUME_EXPERIENCE_DATE_TEMPLATE.format(date_range=date_range))
        if experience.highlights:
            lines.extend(RESUME_EXPERIENCE_LINE_TEMPLATE.format(line=item) for item in experience.highlights)
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)

# This function does render dynamic skills icon blocks.
# It derives language icons from language summary data and tools/platform icons from resume skills.
def render_skill_icons(language_totals: List[tuple], skills: dict, empty_message: str) -> str:
    language_icon_ids = []
    for language, _ in language_totals:
        icon_id = LANGUAGE_ICON_MAP.get((language or "").strip().lower())
        if icon_id:
            language_icon_ids.append(icon_id)

    if not language_icon_ids:
        for language in skills.get("Languages", []):
            icon_id = LANGUAGE_ICON_MAP.get((language or "").strip().lower())
            if icon_id:
                language_icon_ids.append(icon_id)

    language_icon_ids = _dedupe_keep_order(language_icon_ids)

    tools_platform_icon_ids, _ = _collect_tools_platform_icons_and_other(skills)

    language_row = _render_icon_row("Languages", language_icon_ids, "Languages")
    tools_row = _render_icon_row("Tools & Platforms", tools_platform_icon_ids, "Tools & Platforms")

    rows = [row for row in [language_row, tools_row] if row]
    if not rows:
        return empty_message
    return "\n\n".join(rows)

# This function does render non-icon-mapped tools/platforms from resume data.
# It returns a bullet list intended to sit alongside language breakdown.
def render_other_tools(skills: dict, empty_message: str) -> str:
    _, other_tools = _collect_tools_platform_icons_and_other(skills)
    if not other_tools:
        return empty_message
    return "\n".join(OTHER_TOOLS_LINE_TEMPLATE.format(tool=item) for item in other_tools)
