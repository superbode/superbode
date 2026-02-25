#------------------------------------------------------------
#                      readme_service.py
#             Provides helpers to read, write, and
#                  replace README sections.

import re
import sys
from typing import Iterable, Set

SECTION_PATTERN_TEMPLATE = r"({start})\n.*?({end})"
SECTION_REPLACEMENT_TEMPLATE = r"\1\n{body}\n\2"
MISSING_MARKER_WARNING_TEMPLATE = "WARNING: marker pair not found: {marker!r}"
DUPLICATE_MARKER_WARNING_TEMPLATE = "WARNING: duplicate marker pairs found for {marker!r}; collapsing to first occurrence"
DUPLICATE_SECTION_WARNING_TEMPLATE = "WARNING: duplicate generated heading found for {heading!r}; removing extra blocks"

# This function does replace a marker-delimited README block.
# It preserves surrounding content and warns if markers are missing.
def replace_section(content: str, start_marker: str, end_marker: str, new_body: str) -> str:
    pattern = re.compile(
        SECTION_PATTERN_TEMPLATE.format(
            start=re.escape(start_marker),
            end=re.escape(end_marker),
        ),
        re.DOTALL,
    )

    matches = list(pattern.finditer(content))
    if len(matches) > 1:
        print(DUPLICATE_MARKER_WARNING_TEMPLATE.format(marker=start_marker), file=sys.stderr)
        for duplicate in reversed(matches[1:]):
            content = content[:duplicate.start()] + content[duplicate.end():]
        matches = list(pattern.finditer(content))

    replacement = SECTION_REPLACEMENT_TEMPLATE.format(body=new_body)
    result, count = pattern.subn(replacement, content, count=1)
    if count == 0:
        print(MISSING_MARKER_WARNING_TEMPLATE.format(marker=start_marker), file=sys.stderr)
    return result

# This function does load README text from the given path.
# It reads file content as UTF-8 and returns it.
def load_readme(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file_handle:
        return file_handle.read()

# This function does save README text to the given path.
# It writes UTF-8 content to overwrite the target file.
def save_readme(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as file_handle:
        file_handle.write(content)

def _collect_generated_headings(content: str, start_markers: Iterable[str]) -> Set[str]:
    headings: Set[str] = set()
    for marker in start_markers:
        marker_pos = content.find(marker)
        if marker_pos < 0:
            continue
        preceding_headings = list(re.finditer(r"^## .+$", content[:marker_pos], flags=re.MULTILINE))
        if preceding_headings:
            headings.add(preceding_headings[-1].group(0).strip())
    return headings

# This function does remove duplicate generated heading sections.
# It infers headings from marker locations and removes repeated later blocks.
def remove_duplicate_sections(content: str, start_markers: Iterable[str]) -> str:
    updated = content
    generated_headings = _collect_generated_headings(updated, start_markers)

    for heading in generated_headings:
        matches = list(re.finditer(rf"^{re.escape(heading)}$", updated, flags=re.MULTILINE))
        if len(matches) <= 1:
            continue

        print(DUPLICATE_SECTION_WARNING_TEMPLATE.format(heading=heading), file=sys.stderr)
        for duplicate in reversed(matches[1:]):
            start = duplicate.start()
            next_heading = re.search(r"^## ", updated[duplicate.end():], flags=re.MULTILINE)
            end = duplicate.end() + next_heading.start() if next_heading else len(updated)

            prefix_match = re.search(r"\n---\n\n$", updated[:start])
            if prefix_match:
                start = prefix_match.start()

            updated = updated[:start] + updated[end:]

    return re.sub(r"\n{3,}", "\n\n", updated)
