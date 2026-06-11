"""Validate the Odysseus installation and copy skills into it.

The user provides only the Odysseus root folder. Imported skills always
go to ``<root>/data/skills/imported`` — the sibling ``general`` folder
holds skills created manually inside Odysseus and is never touched.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .models import Skill

SKILLS_SUBDIR: tuple[str, ...] = ("data", "skills")
IMPORTED_SUBDIR: tuple[str, ...] = ("data", "skills", "imported")


class SkillImportError(Exception):
    """Raised when a skill cannot be copied into the target directory."""


def resolve_odysseus_root(raw_path: str) -> Path:
    """Normalise *raw_path* and validate it as an Odysseus root folder.

    Windows-style backslashes are accepted on POSIX systems, and paths
    pointing inside the install (``data/skills`` or
    ``data/skills/imported``) are walked back up to the root. Raises
    :class:`SkillImportError` when the result is not a valid Odysseus
    installation.
    """
    raw = raw_path.strip()
    if not raw:
        raise SkillImportError("Please enter the Odysseus root folder")
    if os.sep == "/" and "\\" in raw and "/" not in raw:
        raw = raw.replace("\\", "/")
    path = Path(raw).expanduser().resolve()

    # Accept paths inside the install and walk up to the root.
    parts = [part.lower() for part in path.parts]
    if parts[-3:] == ["data", "skills", "imported"]:
        path = path.parents[2]
    elif parts[-2:] == ["data", "skills"]:
        path = path.parents[1]

    validate_odysseus_root(path)
    return path


def validate_odysseus_root(root: Path) -> None:
    """Raise :class:`SkillImportError` unless *root* is an Odysseus install.

    A valid install is a directory containing ``data/skills``.
    """
    if not root.exists():
        raise SkillImportError(f"{root} does not exist")
    if not root.is_dir():
        raise SkillImportError(f"{root} is not a directory")
    skills_dir = root.joinpath(*SKILLS_SUBDIR)
    if not skills_dir.is_dir():
        raise SkillImportError(
            f"{root} does not look like an Odysseus installation "
            f"(missing {os.sep.join(SKILLS_SUBDIR)})"
        )


def imported_skills_dir(root: Path) -> Path:
    """Directory where imported skills are stored, under a valid root."""
    return root.joinpath(*IMPORTED_SUBDIR)


def import_skill(skill: Skill, target_dir: Path, *, overwrite: bool = False) -> Path:
    """Copy a skill directory into *target_dir* and return the destination.

    Raises :class:`SkillImportError` when the destination already exists
    (unless *overwrite* is set) or the copy fails.
    """
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SkillImportError(f"Cannot create target directory: {exc}") from exc

    destination = target_dir / skill.path.name
    if destination.exists():
        if not overwrite:
            raise SkillImportError(f"'{destination.name}' already exists")
        shutil.rmtree(destination)

    try:
        shutil.copytree(skill.path, destination)
    except OSError as exc:
        raise SkillImportError(f"Copy failed: {exc}") from exc
    return destination
