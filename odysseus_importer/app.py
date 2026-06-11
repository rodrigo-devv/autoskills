"""Application entry point for the Odysseus Skill Importer TUI."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from textual.app import App

from .screens import SetupScreen


class OdysseusImporterApp(App[None]):
    """Terminal-style TUI to import skills from GitHub into Odysseus."""

    TITLE = "Odysseus Skill Importer"
    CSS_PATH = "app.tcss"
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self._workdir: Path | None = None

    @property
    def workdir(self) -> Path:
        """Temporary directory that holds the cloned repositories."""
        if self._workdir is None:
            self._workdir = Path(tempfile.mkdtemp(prefix="odysseus-importer-"))
        return self._workdir

    def on_mount(self) -> None:
        self.push_screen(SetupScreen())

    def on_unmount(self) -> None:
        if self._workdir is not None:
            shutil.rmtree(self._workdir, ignore_errors=True)


def run() -> None:
    """Console-script entry point."""
    OdysseusImporterApp().run()
