"""Skills screen: select skills, confirm, and watch the import progress."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from ..importer import SkillImportError, import_skill
from ..models import ImportStatus, Skill
from ..widgets import SkillRow
from .confirm import ConfirmScreen


class SkillsScreen(Screen[None]):
    """Dynamic list of detected skills with selection and live status."""

    BINDINGS = [
        ("a", "add_all", "Add All"),
        ("space", "select", "Select"),
        ("escape", "cancel", "Back"),
    ]

    def __init__(self, skills: list[Skill], target_dir: Path) -> None:
        super().__init__()
        self._skills = skills
        self._target_dir = target_dir
        self._importing = False
        self._finished = False

    def compose(self) -> ComposeResult:
        yield Static("┌─ DETECTED SKILLS ─┐", id="title")
        yield Static(f"Target: {self._target_dir}", id="target-line")
        with VerticalScroll(id="skill-list"):
            for skill in self._skills:
                yield SkillRow(skill)
        with Horizontal(id="skills-actions"):
            yield Button("Add All", id="add-all")
            yield Button("Select", id="select")
            yield Button("Confirm", id="confirm", variant="primary")
            yield Button("Cancel", id="cancel", variant="error")
        yield Static(self._summary_text(), id="skills-status")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._importing:
            return
        if event.button.id == "add-all":
            self.action_add_all()
        elif event.button.id == "select":
            self.action_select()
        elif event.button.id == "confirm":
            self._confirm()
        elif event.button.id == "cancel":
            self.action_cancel()

    def on_checkbox_changed(self) -> None:
        self._update_summary()

    def action_add_all(self) -> None:
        if self._importing:
            return
        for row in self.query(SkillRow):
            row.set_selected(True)
        self._update_summary()

    def action_select(self) -> None:
        """Toggle the skill row that currently has focus."""
        if self._importing:
            return
        focused = self.focused
        while focused is not None and not isinstance(focused, SkillRow):
            focused = focused.parent if hasattr(focused, "parent") else None
        if isinstance(focused, SkillRow):
            focused.toggle_selected()
            self._update_summary()
        else:
            self.notify("Focus a skill in the list first (Tab / arrow keys).")

    def action_cancel(self) -> None:
        if not self._importing:
            self.app.pop_screen()

    def _confirm(self) -> None:
        selected = [skill for skill in self._skills if skill.selected]
        if not selected:
            self.notify("Select at least one skill to import.", severity="warning")
            return

        def on_decision(confirmed: bool | None) -> None:
            if confirmed:
                self._begin_import(selected)

        self.app.push_screen(
            ConfirmScreen(len(selected), self._target_dir), on_decision
        )

    def _begin_import(self, selected: list[Skill]) -> None:
        self._importing = True
        for button in self.query(Button):
            button.disabled = True
        self._set_status(f"Importing {len(selected)} skill(s)…")
        self._import_worker(selected)

    @work(thread=True, exclusive=True)
    def _import_worker(self, selected: list[Skill]) -> None:
        for skill in selected:
            self.app.call_from_thread(
                self._set_row_status, skill, ImportStatus.IMPORTING, None
            )
            try:
                import_skill(skill, self._target_dir)
            except SkillImportError as exc:
                self.app.call_from_thread(
                    self._set_row_status, skill, ImportStatus.FAILED, str(exc)
                )
            else:
                self.app.call_from_thread(
                    self._set_row_status, skill, ImportStatus.SUCCESS, None
                )
        self.app.call_from_thread(self._on_import_complete, selected)

    def _set_row_status(
        self, skill: Skill, status: ImportStatus, error: str | None
    ) -> None:
        for row in self.query(SkillRow):
            if row.skill is skill:
                row.set_status(status, error)
                break

    def _on_import_complete(self, selected: list[Skill]) -> None:
        self._importing = False
        self._finished = True
        succeeded = sum(1 for s in selected if s.status is ImportStatus.SUCCESS)
        failed = len(selected) - succeeded
        cancel = self.query_one("#cancel", Button)
        cancel.label = "Back"
        cancel.disabled = False
        self._set_status(
            f"Done — {succeeded} succeeded, {failed} failed. "
            f"Skills written to {self._target_dir}. Press Back to return."
        )
        severity = "error" if failed else "information"
        self.notify(f"Import finished: {succeeded} ok, {failed} failed.", severity=severity)

    def _update_summary(self) -> None:
        if not self._importing and not self._finished:
            self._set_status(self._summary_text())

    def _summary_text(self) -> str:
        selected = sum(1 for skill in self._skills if skill.selected)
        return f"{selected} of {len(self._skills)} skill(s) selected."

    def _set_status(self, message: str) -> None:
        self.query_one("#skills-status", Static).update(message)
