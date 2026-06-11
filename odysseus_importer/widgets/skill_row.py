"""A selectable row representing a single skill in the skills list."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Checkbox, Label

from ..models import ImportStatus, Skill

_STATUS_CLASSES: tuple[str, ...] = tuple(status.css_class for status in ImportStatus)


class SkillRow(Horizontal):
    """Checkbox + name/description + live status for one skill."""

    def __init__(self, skill: Skill) -> None:
        super().__init__(classes="skill-row")
        self.skill = skill

    def compose(self) -> ComposeResult:
        yield Checkbox(value=self.skill.selected, classes="skill-check")
        with Vertical(classes="skill-info"):
            yield Label(self.skill.name, classes="skill-name")
            yield Label(self.skill.description, classes="skill-desc")
        yield Label(
            self.skill.status.value,
            classes=f"skill-status {self.skill.status.css_class}",
        )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        event.stop()
        self.skill.selected = event.value

    def set_selected(self, selected: bool) -> None:
        """Update both the model and the visible checkbox."""
        self.skill.selected = selected
        self.query_one(Checkbox).value = selected

    def toggle_selected(self) -> None:
        self.set_selected(not self.skill.selected)

    def set_status(self, status: ImportStatus, error: str | None = None) -> None:
        """Reflect a new import status in the model and the UI."""
        self.skill.status = status
        self.skill.error = error
        label = self.query_one(".skill-status", Label)
        label.update(self.skill.status_text)
        label.remove_class(*_STATUS_CLASSES)
        label.add_class(status.css_class)
