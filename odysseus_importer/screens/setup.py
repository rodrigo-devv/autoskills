"""Setup screen: collect the Odysseus root folder and GitHub repository URLs."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, Static

from ..config import load_cached_root, save_cached_root
from ..importer import SkillImportError, imported_skills_dir, resolve_odysseus_root
from ..models import ScanReport
from ..scanner import is_valid_repo_url, scan_repositories
from .skills import SkillsScreen


class SetupScreen(Screen[None]):
    """First screen: gather inputs and kick off repository scanning."""

    BINDINGS = [("q", "app.quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self._repos: list[str] = []
        self._scanning: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-panel"):
            yield Static("┌─ ODYSSEUS SKILL IMPORTER ─┐", id="title")
            yield Label("Odysseus root folder:")
            with Horizontal(id="dir-bar"):
                yield Input(placeholder="C:\\odysseus", id="dir-input")
                yield Button("Verify", id="verify")
            yield Label("GitHub repository URL:")
            with Horizontal(id="url-bar"):
                yield Input(
                    placeholder="https://github.com/user/skills-repo",
                    id="url-input",
                )
                yield Button("Add Repo", id="add-repo")
            yield Static("No repositories added yet.", id="repo-list")
            with Horizontal(id="setup-actions"):
                yield Button("Scan Skills", id="scan", variant="primary")
                yield Button("Quit", id="quit", variant="error")
            yield Static("", id="setup-status")
        yield Footer()

    def on_mount(self) -> None:
        cached = load_cached_root()
        if cached:
            self.query_one("#dir-input", Input).value = cached
            self._verify_root(quiet=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._scanning:
            return
        if event.button.id == "verify":
            self._verify_root()
        elif event.button.id == "add-repo":
            self._add_repo()
        elif event.button.id == "scan":
            self._start_scan()
        elif event.button.id == "quit":
            self.app.exit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._scanning:
            return
        if event.input.id == "url-input":
            self._add_repo()
        elif event.input.id == "dir-input":
            self._verify_root()

    def _verify_root(self, *, quiet: bool = False) -> Path | None:
        """Validate the Odysseus root input; cache and report on success."""
        raw = self.query_one("#dir-input", Input).value
        try:
            root = resolve_odysseus_root(raw)
        except SkillImportError as exc:
            if not quiet:
                self._set_status(f"✗ {exc}", error=True)
            return None
        save_cached_root(root)
        self._set_status(
            f"✓ Valid Odysseus folder. Skills will be imported into "
            f"{imported_skills_dir(root)}"
        )
        return root

    def _add_repo(self) -> None:
        url_input = self.query_one("#url-input", Input)
        url = url_input.value.strip()
        if not url:
            return
        if not is_valid_repo_url(url):
            self._set_status("Invalid repository URL (expected https://, git@ or ssh://).", error=True)
            return
        if url in self._repos:
            self._set_status("Repository already in the list.", error=True)
            return
        self._repos.append(url)
        url_input.value = ""
        self._refresh_repo_list()
        self._set_status(f"Added {url}")

    def _refresh_repo_list(self) -> None:
        listing = "\n".join(f"  • {url}" for url in self._repos)
        self.query_one("#repo-list", Static).update(
            listing or "No repositories added yet."
        )

    def _start_scan(self) -> None:
        root = self._verify_root()
        if root is None:
            return
        target_dir = imported_skills_dir(root)

        # Treat an un-added URL still sitting in the input as part of the list.
        pending = self.query_one("#url-input", Input).value.strip()
        if pending:
            self._add_repo()
        if not self._repos:
            self._set_status("Please add at least one GitHub repository URL.", error=True)
            return

        self._scanning = True
        self._set_buttons_disabled(True)
        self._set_status(f"Cloning {len(self._repos)} repositor{'y' if len(self._repos) == 1 else 'ies'}…")
        self._scan_worker(list(self._repos), target_dir)

    @work(thread=True, exclusive=True)
    def _scan_worker(self, urls: list[str], target_dir: Path) -> None:
        report = scan_repositories(urls, self.app.workdir)
        self.app.call_from_thread(self._on_scan_complete, report, target_dir)

    def _on_scan_complete(self, report: ScanReport, target_dir: Path) -> None:
        self._scanning = False
        self._set_buttons_disabled(False)
        for error in report.errors:
            self.notify(error, severity="warning", timeout=8)
        if not report.skills:
            self._set_status("No skills found. Check the errors above and try again.", error=True)
            return
        self._set_status(f"Found {len(report.skills)} skill(s).")
        self.app.push_screen(SkillsScreen(report.skills, target_dir))

    def _set_buttons_disabled(self, disabled: bool) -> None:
        for button in self.query(Button):
            button.disabled = disabled

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#setup-status", Static)
        status.update(message)
        status.set_class(error, "error-text")
