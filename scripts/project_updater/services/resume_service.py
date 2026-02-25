#------------------------------------------------------------
#                     resume_service.py
#         Extracts resume content from a local PDF.

import os
import re
from typing import Dict, List, Optional
from ..models import ResumeSnapshot

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

MONTH_PATTERN = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_RANGE_PATTERN = re.compile(
    rf"{MONTH_PATTERN}\s+\d{{4}}(?:\s*[-–]\s*|\s{{2,}})(?:{MONTH_PATTERN}\s+\d{{4}}|Present)",
    re.IGNORECASE,
)
SKILL_CATEGORY_PATTERN = re.compile(
    r"^(languages?|programming languages?|tools?|platforms?|frameworks?|databases?|project management)\s*[:\-]\s*(.+)$",
    re.IGNORECASE,
)
HEADING_LIKE_PATTERN = re.compile(r"^[A-Z][A-Z\s/&]{2,}$")
PUNCT_SPACING_PATTERN = re.compile(r"\s+([,.;:])")

KNOWN_HEADINGS = {
    "professional experience",
    "experience",
    "work experience",
    "employment",
    "technical skills",
    "technical experience",
    "skills",
    "education",
    "projects",
    "activities",
    "leadership",
    "certifications",
    "awards",
}

EXPERIENCE_START_HEADINGS = (
    "technical experience",
    "professional experience",
    "work experience",
    "employment",
)
EXPERIENCE_END_HEADINGS = (
    "education",
    "skills",
    "technical skills",
    "projects",
    "activities",
    "leadership",
    "honors and activities",
    "honors",
    "certifications",
    "awards",
)
SKILLS_START_HEADINGS = ("technical skills", "skills")
SKILLS_END_HEADINGS = ("experience", "professional experience", "work experience", "employment", "education", "projects", "activities", "leadership", "certifications", "awards")

SKILL_CATEGORY_LABELS = {
    "language": "Languages",
    "languages": "Languages",
    "programming language": "Languages",
    "programming languages": "Languages",
    "tool": "Tools",
    "tools": "Tools",
    "platform": "Platforms",
    "platforms": "Platforms",
    "framework": "Frameworks",
    "frameworks": "Frameworks",
    "database": "Databases",
    "databases": "Databases",
    "project management": "Platforms",
}

DEFAULT_SKILL_ORDER = ["Languages", "Tools", "Platforms", "Frameworks", "Databases"]

def _normalize_line(text: str) -> str:
    value = (text or "").replace("\u2022", "-").replace("•", "-").strip()
    value = PUNCT_SPACING_PATTERN.sub(r"\1", value)
    value = re.sub(r"\s+", " ", value)
    return value

def _is_heading(line: str) -> bool:
    lowered = line.strip().lower()
    if lowered in KNOWN_HEADINGS:
        return True
    if len(lowered.split()) <= 4 and HEADING_LIKE_PATTERN.match(line.strip()):
        return True
    return False

def _find_heading_index(lines: List[str], headings: tuple) -> Optional[int]:
    lowered_headings = tuple(item.lower() for item in headings)
    for index, line in enumerate(lines):
        lowered = line.lower()
        for heading in lowered_headings:
            if lowered == heading or lowered.startswith(f"{heading}:"):
                return index
    return None

def _extract_section_lines(lines: List[str], start_heading: str, end_headings: tuple) -> List[str]:
    start_index = _find_heading_index(lines, (start_heading,))
    if start_index is None:
        return []

    section_lines: List[str] = []
    end_heading_set = {item.lower() for item in end_headings}
    for candidate in lines[start_index + 1:]:
        lowered = candidate.lower()
        if lowered in end_heading_set and _is_heading(candidate):
            break
        section_lines.append(candidate)
    return section_lines

def _extract_combined_sections(lines: List[str], start_headings: tuple, end_headings: tuple) -> List[str]:
    combined: List[str] = []
    for heading in start_headings:
        section_lines = _extract_section_lines(lines, heading, end_headings)
        if section_lines:
            combined.extend(section_lines)
    return combined

def _extract_experience_lines(lines: List[str]) -> List[str]:
    section = _extract_combined_sections(lines, EXPERIENCE_START_HEADINGS, EXPERIENCE_END_HEADINGS)
    source = section if section else lines

    entries: List[str] = []
    for index, line in enumerate(source):
        if DATE_RANGE_PATTERN.search(line):
            entry = line
            previous = source[index - 1] if index > 0 else ""
            if previous and not previous.startswith("-") and not DATE_RANGE_PATTERN.search(previous) and not _is_heading(previous):
                entry = f"{previous} — {entry}"
            if entry.startswith("-"):
                entry = entry[1:].strip()
            if len(entry) >= 10:
                entries.append(entry)
        if len(entries) >= 8:
            break

    if entries:
        deduped: List[str] = []
        seen = set()
        for item in entries:
            key = item.lower()
            if key in seen:
                continue
            deduped.append(item)
            seen.add(key)
        return deduped

    fallback: List[str] = []
    for line in section:
        if len(line) < 16:
            continue
        if line.startswith("-"):
            continue
        fallback.append(line)
        if len(fallback) >= 6:
            break
    return fallback

def _split_items(raw_items: str) -> List[str]:
    chunks = re.split(r"[,|;/]", raw_items)
    return [item.strip() for item in chunks if item.strip()]

def _extract_skills(lines: List[str]) -> Dict[str, List[str]]:
    section = _extract_combined_sections(lines, SKILLS_START_HEADINGS, SKILLS_END_HEADINGS)
    source = section if section else lines

    found: Dict[str, List[str]] = {}
    seen = set()
    for line in source:
        match = SKILL_CATEGORY_PATTERN.match(line)
        if not match:
            continue

        category = match.group(1).strip().lower()
        canonical_category = SKILL_CATEGORY_LABELS.get(category, category.title())
        items = _split_items(match.group(2))
        if not items:
            continue

        bucket = found.setdefault(canonical_category, [])
        for item in items:
            key = (canonical_category.lower(), item.lower())
            if key in seen:
                continue
            bucket.append(item)
            seen.add(key)

    ordered: Dict[str, List[str]] = {}
    for category in DEFAULT_SKILL_ORDER:
        if category in found:
            ordered[category] = found[category]
    for category, items in found.items():
        if category not in ordered:
            ordered[category] = items
    return ordered

def extract_resume_snapshot(pdf_path: str) -> ResumeSnapshot:
    if not pdf_path or not os.path.exists(pdf_path) or PdfReader is None:
        return ResumeSnapshot(experiences=[], skills={})

    try:
        reader = PdfReader(pdf_path)
    except Exception:
        return ResumeSnapshot(experiences=[], skills={})

    text_lines: List[str] = []
    for page in reader.pages:
        try:
            extracted = page.extract_text() or ""
        except Exception:
            extracted = ""

        for raw_line in extracted.splitlines():
            normalized = _normalize_line(raw_line)
            if normalized:
                text_lines.append(normalized)

    return ResumeSnapshot(
        experiences=_extract_experience_lines(text_lines),
        skills=_extract_skills(text_lines),
    )