#------------------------------------------------------------
#                      readme_service.py
#             Provides helpers to read, write, and
#                  replace README sections.

import re
import sys

# This function does replace a marker-delimited README block.
# It preserves surrounding content and warns if markers are missing.
def replace_section(content: str, start_marker: str, end_marker: str, new_body: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start_marker)})\n.*?({re.escape(end_marker)})",
        re.DOTALL,
    )
    replacement = rf"\1\n{new_body}\n\2"
    result, count = pattern.subn(replacement, content)
    if count == 0:
        print(f"WARNING: marker pair not found: {start_marker!r}", file=sys.stderr)
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
