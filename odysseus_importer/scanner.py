"""Clone GitHub repositories and detect the skills they contain.

A *skill* is detected in two ways, in order of preference:

1. Any directory containing a ``SKILL.md`` manifest. Name and description
   are read from the YAML front matter when present, falling back to the
   directory name and the first paragraph of the document.
2. If no manifest is found, directories that live under a ``skills/``
   folder (or directly under the repository root) and contain a
   ``README.md`` are treated as skills.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .models import ScanReport, Skill

CLONE_TIMEOUT_SECONDS: int = 180
MAX_DESCRIPTION_LENGTH: int = 120

_GIT_URL_RE = re.compile(r"^(https?://|git@|ssh://)\S+$")
_FRONTMATTER_LINE_RE = re.compile(r"^(?P<key>[A-Za-z_][\w-]*)\s*:\s*(?P<value>.*)$")


class ScanError(Exception):
    """Raised when a repository cannot be cloned or scanned."""


def is_valid_repo_url(url: str) -> bool:
    """Return ``True`` if *url* looks like a git repository URL."""
    return bool(_GIT_URL_RE.match(url.strip()))


def repo_slug(url: str) -> str:
    """Derive a filesystem-friendly name from a repository URL."""
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    tail = tail.removesuffix(".git")
    slug = re.sub(r"[^\w.-]", "-", tail)
    return slug or "repository"


def clone_repository(url: str, workdir: Path) -> Path:
    """Shallow-clone *url* into a unique directory under *workdir*."""
    target = workdir / repo_slug(url)
    counter = 1
    while target.exists():
        target = workdir / f"{repo_slug(url)}-{counter}"
        counter += 1

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target)],
            check=True,
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise ScanError("git is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ScanError(f"Timed out cloning {url}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip().splitlines()
        reason = detail[-1] if detail else "unknown git error"
        raise ScanError(f"Failed to clone {url}: {reason}") from exc
    return target


def scan_repository(repo_dir: Path, repo_url: str) -> list[Skill]:
    """Detect every skill inside an already-cloned repository."""
    skills = _scan_manifests(repo_dir, repo_url)
    if not skills:
        skills = _scan_conventional_layout(repo_dir, repo_url)
    return sorted(skills, key=lambda skill: skill.name.lower())


def scan_repositories(urls: list[str], workdir: Path) -> ScanReport:
    """Clone and scan every repository URL, collecting skills and errors."""
    report = ScanReport()
    for url in urls:
        try:
            repo_dir = clone_repository(url, workdir)
            found = scan_repository(repo_dir, url)
        except ScanError as exc:
            report.errors.append(str(exc))
            continue
        if found:
            report.skills.extend(found)
        else:
            report.errors.append(f"No skills detected in {url}")
    return report


def _scan_manifests(repo_dir: Path, repo_url: str) -> list[Skill]:
    skills: list[Skill] = []
    for manifest in sorted(repo_dir.rglob("SKILL.md")):
        if ".git" in manifest.parts:
            continue
        skill_dir = manifest.parent
        if skill_dir == repo_dir:
            continue
        meta = _parse_frontmatter(_read_text(manifest))
        name = meta.get("name") or skill_dir.name
        description = meta.get("description") or _first_paragraph(manifest)
        skills.append(
            Skill(
                name=name,
                description=_truncate(description),
                path=skill_dir,
                repo_url=repo_url,
            )
        )
    return skills


def _scan_conventional_layout(repo_dir: Path, repo_url: str) -> list[Skill]:
    candidates: list[Path] = []
    skills_root = repo_dir / "skills"
    roots = [skills_root] if skills_root.is_dir() else [repo_dir]
    for root in roots:
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and not entry.name.startswith(".") and (entry / "README.md").is_file():
                candidates.append(entry)
    return [
        Skill(
            name=candidate.name,
            description=_truncate(_first_paragraph(candidate / "README.md")),
            path=candidate,
            repo_url=repo_url,
        )
        for candidate in candidates
    ]


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the simple ``key: value`` YAML front matter of a manifest."""
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() in {"---", "..."}:
            break
        match = _FRONTMATTER_LINE_RE.match(line)
        if match:
            meta[match.group("key").lower()] = match.group("value").strip().strip("\"'")
    return meta


def _first_paragraph(markdown_file: Path) -> str:
    """Return the first non-heading paragraph of a markdown file."""
    text = _read_text(markdown_file)
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    for block in text.split("\n\n"):
        stripped = " ".join(block.split())
        if stripped and not stripped.startswith("#"):
            return stripped
    return "No description available"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _truncate(text: str, limit: int = MAX_DESCRIPTION_LENGTH) -> str:
    text = text.strip() or "No description available"
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
