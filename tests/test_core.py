"""Unit tests for the scanner and importer modules."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from odysseus_importer import config
from odysseus_importer.importer import (
    SkillImportError,
    import_skill,
    imported_skills_dir,
    resolve_odysseus_root,
)
from odysseus_importer.models import ImportStatus, Skill
from odysseus_importer.scanner import (
    is_valid_repo_url,
    repo_slug,
    scan_repository,
)


def make_skill_dir(root: Path, name: str, description: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill_dir


class TestUrlValidation:
    def test_accepts_common_forms(self) -> None:
        assert is_valid_repo_url("https://github.com/user/repo")
        assert is_valid_repo_url("git@github.com:user/repo.git")
        assert is_valid_repo_url("ssh://git@github.com/user/repo")

    def test_rejects_garbage(self) -> None:
        assert not is_valid_repo_url("")
        assert not is_valid_repo_url("not a url")
        assert not is_valid_repo_url("ftp://example.com/repo")

    def test_repo_slug(self) -> None:
        assert repo_slug("https://github.com/user/my-skills.git") == "my-skills"
        assert repo_slug("https://github.com/user/my-skills/") == "my-skills"


class TestScanner:
    def test_detects_skill_manifests(self, tmp_path: Path) -> None:
        make_skill_dir(tmp_path, "alpha", "First skill")
        make_skill_dir(tmp_path / "nested", "beta", "Second skill")

        skills = scan_repository(tmp_path, "https://example.com/repo")

        assert [s.name for s in skills] == ["alpha", "beta"]
        assert skills[0].description == "First skill"
        assert all(s.status is ImportStatus.PENDING for s in skills)

    def test_frontmatter_fallbacks(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "no-meta"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# Title\n\nThe first paragraph describes it.\n", encoding="utf-8"
        )

        skills = scan_repository(tmp_path, "url")

        assert skills[0].name == "no-meta"
        assert skills[0].description == "The first paragraph describes it."

    def test_conventional_layout_fallback(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "skills" / "gamma"
        skill_dir.mkdir(parents=True)
        (skill_dir / "README.md").write_text("# Gamma\n\nDoes gamma things.\n", encoding="utf-8")

        skills = scan_repository(tmp_path, "url")

        assert [s.name for s in skills] == ["gamma"]
        assert skills[0].description == "Does gamma things."

    def test_empty_repo_yields_nothing(self, tmp_path: Path) -> None:
        assert scan_repository(tmp_path, "url") == []


class TestImporter:
    def make_skill(self, tmp_path: Path) -> Skill:
        skill_dir = make_skill_dir(tmp_path / "clone", "alpha", "First skill")
        return Skill(name="alpha", description="First skill", path=skill_dir, repo_url="url")

    def test_copies_skill_into_target(self, tmp_path: Path) -> None:
        skill = self.make_skill(tmp_path)
        target = tmp_path / "odysseus"

        destination = import_skill(skill, target)

        assert destination == target / "alpha"
        assert (destination / "SKILL.md").is_file()

    def test_refuses_to_overwrite_existing(self, tmp_path: Path) -> None:
        skill = self.make_skill(tmp_path)
        target = tmp_path / "odysseus"
        (target / "alpha").mkdir(parents=True)

        with pytest.raises(SkillImportError, match="already exists"):
            import_skill(skill, target)

    def test_overwrite_flag(self, tmp_path: Path) -> None:
        skill = self.make_skill(tmp_path)
        target = tmp_path / "odysseus"
        (target / "alpha").mkdir(parents=True)

        destination = import_skill(skill, target, overwrite=True)

        assert (destination / "SKILL.md").is_file()


def make_odysseus_root(tmp_path: Path) -> Path:
    root = tmp_path / "odysseus"
    (root / "data" / "skills" / "general").mkdir(parents=True)
    return root


class TestOdysseusRoot:
    def test_accepts_valid_root(self, tmp_path: Path) -> None:
        root = make_odysseus_root(tmp_path)

        resolved = resolve_odysseus_root(str(root))

        assert resolved == root.resolve()
        assert resolved.is_absolute()

    def test_rejects_missing_data_skills(self, tmp_path: Path) -> None:
        plain = tmp_path / "not-odysseus"
        plain.mkdir()

        with pytest.raises(SkillImportError, match="does not look like an Odysseus"):
            resolve_odysseus_root(str(plain))

    def test_rejects_missing_directory(self, tmp_path: Path) -> None:
        with pytest.raises(SkillImportError, match="does not exist"):
            resolve_odysseus_root(str(tmp_path / "nowhere"))

    def test_rejects_empty_input(self) -> None:
        with pytest.raises(SkillImportError, match="enter the Odysseus root"):
            resolve_odysseus_root("   ")

    def test_walks_up_from_data_skills(self, tmp_path: Path) -> None:
        root = make_odysseus_root(tmp_path)

        assert resolve_odysseus_root(str(root / "data" / "skills")) == root.resolve()

    def test_walks_up_from_imported(self, tmp_path: Path) -> None:
        root = make_odysseus_root(tmp_path)
        (root / "data" / "skills" / "imported").mkdir()

        path = root / "data" / "skills" / "imported"
        assert resolve_odysseus_root(str(path)) == root.resolve()

    def test_accepts_backslash_paths(self, tmp_path: Path) -> None:
        if os.sep != "/":
            pytest.skip("POSIX-only backslash normalisation")
        root = make_odysseus_root(tmp_path)
        windows_style = str(root).replace("/", "\\")

        assert resolve_odysseus_root(windows_style) == root.resolve()

    def test_imported_skills_dir(self, tmp_path: Path) -> None:
        root = make_odysseus_root(tmp_path)

        assert imported_skills_dir(root) == root / "data" / "skills" / "imported"


class TestConfigCache:
    def test_round_trip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setattr(os, "name", "posix")

        config.save_cached_root(Path("/opt/odysseus"))

        assert config.load_cached_root() == "/opt/odysseus"

    def test_missing_cache_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty"))
        monkeypatch.setattr(os, "name", "posix")

        assert config.load_cached_root() is None

    def test_corrupt_cache_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setattr(os, "name", "posix")
        config.config_file().parent.mkdir(parents=True, exist_ok=True)
        config.config_file().write_text("{not json", encoding="utf-8")

        assert config.load_cached_root() is None
