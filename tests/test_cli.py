"""CLI tests via Typer's CliRunner."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ragcli import __version__
from ragcli.cli.app import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_menu_renders_without_command() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "rag init" in result.output


def test_init_yes_is_fully_non_interactive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    # No stdin available — any prompt would crash with EOFError.
    result = runner.invoke(app, ["init", "--yes"], input=None)
    assert result.exit_code == 0, result.output
    assert (tmp_path / "rag.config.toml").exists()
    assert (tmp_path / ".rag").is_dir()
    assert (tmp_path / "docs").is_dir()


def test_init_yes_never_runs_installers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    import subprocess

    real_run = subprocess.run

    def spy_run(cmd, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(cmd if isinstance(cmd, list) else [cmd])
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy_run)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Popen called"))

    result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    # `ollama list` (a read-only status check) is the only acceptable call.
    for cmd in calls:
        flat = " ".join(str(c) for c in cmd)
        assert "install" not in flat and "curl" not in flat and "sudo" not in flat, flat


def test_ingest_missing_dir_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["ingest", "./nope"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_serve_refuses_remote_host_without_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code == 1
    assert "allow-remote" in result.output
