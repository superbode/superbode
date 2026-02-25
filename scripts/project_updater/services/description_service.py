#------------------------------------------------------------
#                   description_service.py
#           Builds concise repository summaries and
#                      language labels.

import re
from typing import Dict, List, Tuple

# This function does clean markdown and HTML artifacts from text.
# It normalizes whitespace for downstream sentence processing.
def clean_text(text: str) -> str:
    cleaned = text or ""
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"`+", "", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"^[#>*\-\s]+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

# This function does split text into sentence candidates.
# It returns non-empty sentence strings.
def split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]

# This function does trim and normalize a sentence length.
# It removes duplicated runs and ensures a trailing period.
def clamp_sentence(sentence: str, max_words: int = 24) -> str:
    words = re.findall(r"[A-Za-z0-9+#.-]+", sentence)

    for size in range(6, 1, -1):
        if len(words) >= size * 2 and words[:size] == words[size:size * 2]:
            words = words[:size] + words[size * 2:]
            break

    if len(words) > max_words:
        words = words[:max_words]
    if not words:
        return ""

    clamped = " ".join(words)
    if not clamped.endswith("."):
        clamped += "."
    return clamped

# This function does score candidate sentence quality.
# It rewards useful wording and penalizes boilerplate text.
def sentence_quality_score(sentence: str) -> int:
    lowered = sentence.lower()
    words = re.findall(r"[A-Za-z0-9+#.-]+", sentence)
    if len(words) < 7:
        return -100

    bad_patterns = [
        "installation",
        "contributing",
        "license",
        "make sure to sign in",
        "before starting this assignment",
        "assignment",
        "setup",
        "contributors list",
        "username",
        "please go through this link",
        "------------",
        "focuses on software engineering",
        "development workflows",
        "contains implementation details",
        "table of contents",
        "badge",
    ]
    if any(pattern in lowered for pattern in bad_patterns):
        return -50

    score = 0
    good_keywords = [
        "is",
        "builds",
        "provides",
        "implements",
        "allows",
        "application",
        "tool",
        "platform",
        "simulator",
        "game",
        "analy",
    ]
    for key in good_keywords:
        if key in lowered:
            score += 8

    score += max(0, 20 - abs(14 - len(words)))
    return score

# This function does choose the strongest sentence from inputs.
# It ranks candidates and returns a clamped best result.
def choose_best_sentence(*texts: str) -> str:
    candidates = []
    for text in texts:
        cleaned = clean_text(text)
        candidates.extend(split_sentences(cleaned))

    if not candidates:
        return ""

    ranked = sorted(candidates, key=sentence_quality_score, reverse=True)
    best = ranked[0]
    if sentence_quality_score(best) < 0:
        return ""
    return clamp_sentence(best)

# This function does build a fallback repository description.
# It uses repo name and primary language when no summary exists.
def fallback_description(repo: dict) -> str:
    name = repo.get("name", "This repository")
    primary = repo.get("language") or "software"
    return f"{name} is a {primary} project with clear goals and practical implementation details."

# This function does infer framework names from context text.
# It returns framework counts sorted by frequency.
def infer_frameworks(text: str) -> List[Tuple[str, int]]:
    keywords = {
        "react": "React",
        "next.js": "Next.js",
        "nextjs": "Next.js",
        "vue": "Vue",
        "angular": "Angular",
        "django": "Django",
        "flask": "Flask",
        "fastapi": "FastAPI",
        "spring": "Spring",
        "laravel": "Laravel",
        "express": "Express",
        "node": "Node.js",
        "microservice": "Microservices",
        "microservices": "Microservices",
        "mvc": "MVC",
        "rest": "REST API",
        "graphql": "GraphQL",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "azure": "Azure",
        "unity": "Unity",
        "shaderlab": "ShaderLab",
    }

    scores: Dict[str, int] = {}
    lowered = (text or "").lower()
    for key, value in keywords.items():
        count = lowered.count(key)
        if count > 0:
            scores[value] = scores.get(value, 0) + count

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)

# This function does select the final repository description.
# It prioritizes overrides, then description text, then fallback.
def select_description(repo: dict, context_text: str, overrides: Dict[str, str]) -> str:
    override = overrides.get((repo.get("name") or "").strip().lower())
    if override:
        return clamp_sentence(override)

    about = clean_text(repo.get("description") or "")
    if about and sentence_quality_score(about) >= 0:
        return clamp_sentence(about, max_words=18)

    best = choose_best_sentence(context_text)
    return best or fallback_description(repo)

# This function does compose displayed language and framework labels.
# It merges ranked language usage with inferred frameworks.
def select_languages(
    language_usage: List[Tuple[str, int]],
    context_text: str,
    uses_cap: int,
) -> str:
    framework_usage = infer_frameworks(context_text)
    merged: List[str] = []
    seen = set()

    for language, _ in language_usage:
        if language and language not in seen:
            merged.append(language)
            seen.add(language)
        if len(merged) >= uses_cap:
            break

    if len(merged) < uses_cap:
        for framework, _ in framework_usage:
            if framework and framework not in seen:
                merged.append(framework)
                seen.add(framework)
            if len(merged) >= uses_cap:
                break

    return ", ".join(merged) if merged else "Not specified"
