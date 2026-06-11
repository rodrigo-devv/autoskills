"""Data models for the Odysseus Skill Importer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ImportStatus(str, Enum):
    """Lifecycle status of a skill during the import process."""

    PENDING = "Pending"
    IMPORTING = "Importing"
    SUCCESS = "Success"
    FAILED = "Failed"

    @property
    def css_class(self) -> str:
        """CSS class used to colour the status label in the TUI."""
        return f"status-{self.name.lower()}"


@dataclass
class Skill:
    """A skill discovered inside a cloned GitHub repository."""

    name: str
    description: str
    path: Path
    repo_url: str
    selected: bool = False
    status: ImportStatus = ImportStatus.PENDING
    error: str | None = None

    @property
    def status_text(self) -> str:
        """Human readable status, including the error message on failure."""
        if self.status is ImportStatus.FAILED and self.error:
            return f"{self.status.value}: {self.error}"
        return self.status.value


@dataclass
class ScanReport:
    """Result of scanning one or more repositories."""

    skills: list[Skill] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
