#------------------------------------------------------------
#                      readme_service.py
#             Provides helpers to read, write, and
#                  replace README sections.

import re
import sys

SECTION_PATTERN_TEMPLATE = r"({start})\n.*?({end})"
SECTION_REPLACEMENT_TEMPLATE = r"\1\n{body}\n\2"
MISSING_MARKER_WARNING_TEMPLATE = "WARNING: marker pair not found: {marker!r}"
DUPLICATE_MARKER_WARNING_TEMPLATE = "WARNING: duplicate marker pairs found for {marker!r}; collapsing to first occurrence"

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
