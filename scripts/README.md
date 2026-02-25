# Scripts Backend Architecture

This folder contains the backend automation that updates generated sections in the profile `README.md`.

## Overview

The updater now follows an MVC-inspired structure:

- **Controller**: orchestrates the workflow and data flow.
- **Models**: defines structured in-memory data objects.
- **Views**: renders markdown output blocks.
- **Services**: handles GitHub API, text processing, and README I/O.
- **Config JSONs**: declarative behavior controls (overrides and ignore lists).

---

## Entry Point

### `project_updater/__main__.py`
- Primary package entrypoint.
- Execute with `PYTHONPATH=scripts python -m project_updater`.

---

## MVC Modules

### `project_updater/controller.py` (Controller)
- Loads runtime config/environment.
- Fetches repositories from GitHub.
- Applies filters and deduplication.
- Splits repos into Current/Past by recent activity window.
- Builds presentation objects and writes generated README sections.

### `project_updater/models.py` (Models)
- `UpdateConfig`: runtime settings (username, token, limits).
- `RepoPresentation`: normalized data for markdown rendering.

### `project_updater/views/markdown_view.py` (Views)
- Renders repo blocks for Current/Past sections.
- Renders language breakdown markdown list.

### `project_updater/services/github_service.py` (Services)
- GitHub API communication.
- Fetches repositories, README text, language usage, contributor counts.
- Caches expensive API lookups for a single run.

### `project_updater/services/description_service.py` (Services)
- Cleans README/description text.
- Scores and selects sentence candidates.
- Applies override-first summary strategy.
- Infers frameworks and composes language stacks.

### `project_updater/services/readme_service.py` (Services)
- Reads and writes root README.
- Replaces marker-delimited generated sections safely.

### `project_updater/config.py`
- Centralized filesystem paths.
- JSON config loading helpers.

---

## Config JSONs (`scripts/config/`)

### `repo_description_overrides.json`
- Maps repo name -> custom one-sentence description.
- Keys are matched case-insensitively.
- Use this for repos where automatic summary selection is imperfect.

### `repo_ignore_list.json`
- List of repo names to exclude entirely from generated Current/Past sections.
- Matched case-insensitively.

### `language_ignore_list.json`
- List of language names to exclude from generated language breakdown.
- Matched case-insensitively.

---

## Typical Flow

1. GitHub Action runs `PYTHONPATH=scripts python -m project_updater`.
2. Controller loads JSON configs and environment variables.
3. GitHub service fetches repo data and metadata.
4. Description/language services produce curated display data.
5. View layer renders markdown blocks.
6. README service updates only marker sections.

---

## Notes

- The main root `README.md` should still be edited manually for static content only.
- Generated sections are managed by the updater and overwritten on each run.
- Keep JSON files valid strict JSON (no comments).
