from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _smoke_module():
    path = ROOT / "scripts" / "smoke_readme.py"
    spec = importlib.util.spec_from_file_location("smoke_readme", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_every_readme_shell_command_is_classified_and_syntax_checked() -> None:
    module = _smoke_module()
    commands = module.commands_from_readme()
    module.validate(commands)
    assert commands
    assert {command.mode for command in commands} == {
        "configure",
        "local",
        "docker",
        "live",
        "teardown",
    }


def test_readme_covers_required_learner_commands() -> None:
    sources = "\n".join(
        command.source for command in _smoke_module().commands_from_readme()
    )
    required = [
        "docker compose up -d",
        "customer-enrichment doctor",
        "customer-enrichment setup",
        "customer-enrichment customers",
        "customer-enrichment enrich --customer-id demo-001 --verbose",
        "customer-enrichment enrich --limit 4",
        "customer-enrichment results",
        "clickhouse-client --query",
        "--force",
        "uv run pytest",
        "customer-enrichment reset --yes",
    ]
    for command in required:
        assert command in sources


def test_teardown_is_separate_from_docker_setup() -> None:
    commands = _smoke_module().commands_from_readme()
    docker_sources = [command.source for command in commands if command.mode == "docker"]
    teardown_sources = [
        command.source for command in commands if command.mode == "teardown"
    ]

    assert "docker compose down" not in docker_sources
    assert teardown_sources == ["docker compose down"]


def test_live_checkpoint_is_bound_to_exact_command_list(monkeypatch, tmp_path) -> None:
    module = _smoke_module()
    module.ROOT = tmp_path
    monkeypatch.setenv("CONFIRM_LIVE_SPEND", "YES")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-only-placeholder")
    monkeypatch.setattr(module, "require_live_prerequisites", lambda: None)
    progress = tmp_path / ".artifacts" / "readme-live-smoke.progress.json"
    progress.parent.mkdir(parents=True)
    progress.write_text(
        json.dumps(
            {"command_fingerprint": "stale", "completed_commands": 1}
        )
    )

    with pytest.raises(SystemExit, match="command list changed"):
        module.execute("live", [module.Command("live", "true")])


def test_command_fingerprint_changes_with_command_source() -> None:
    module = _smoke_module()
    original = [module.Command("live", "true")]
    changed = [module.Command("live", "echo changed")]

    assert module.command_fingerprint(original) == module.command_fingerprint(original)
    assert module.command_fingerprint(original) != module.command_fingerprint(changed)
