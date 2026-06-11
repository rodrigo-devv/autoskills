"""Modal confirmation dialog shown before the import starts."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen[bool]):
    """Ask the user to confirm importing the selected skills."""

    BINDINGS = [("escape", "dismiss(False)", "Cancel")]

    def __init__(self, count: int, target_dir: Path) -> None:
        super().__init__()
        self._count = count
        self._target_dir = target_dir

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static("┌─ CONFIRM IMPORT ─┐", id="confirm-title")
            yield Static(
                f"Import {self._count} skill(s) into:\n{self._target_dir}",
                id="confirm-message",
            )
            with Horizontal(id="confirm-actions"):
                yield Button("Confirm", id="yes", variant="primary")
                yield Button("Cancel", id="no", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")
