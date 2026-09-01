from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.mdx"
SHELL = shutil.which("bash") or "/bin/sh"
MODES = {"configure", "local", "docker", "live", "teardown"}


@dataclass(frozen=True)
class Command:
    mode: str
    source: str


def commands_from_readme() -> list[Command]:
    lines = README.read_text().splitlines()
    commands: list[Command] = []
    pending_mode: str | None = None
    in_bash = False
    buffer: list[str] = []

    for line in lines:
        marker = re.fullmatch(r"\{/\* smoke:(\w+) \*/\}", line.strip())
        if marker:
            pending_mode = marker.group(1)
            continue
        if line.strip() == "```bash":
            if pending_mode not in MODES:
                raise ValueError("Every bash block must have a valid smoke marker")
            in_bash = True
            buffer = []
            continue
        if in_bash and line.strip() == "```":
            source = "\n".join(buffer).strip()
            if not source:
                raise ValueError("Empty bash block")
            commands.append(Command(pending_mode or "", source))
            pending_mode = None
            in_bash = False
            continue
        if in_bash:
            buffer.append(line)
    if in_bash:
        raise ValueError("Unclosed bash block")
    return commands


def validate(commands: list[Command]) -> None:
    for command in commands:
        if "PERPLEXITY_API_KEY" + "=" in command.source:
            raise ValueError("README commands must never contain an API key assignment")
        subprocess.run(
            [SHELL, "-n", "-c", command.source],
            check=True,
            cwd=ROOT,
        )


def command_fingerprint(commands: list[Command]) -> str:
    serialized = json.dumps(
        [{"mode": command.mode, "source": command.source} for command in commands],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def require_live_prerequisites() -> None:
    from customer_enrichment.clickhouse import ClickHouseRepository
    from customer_enrichment.config import Settings

    try:
        repository = ClickHouseRepository(Settings.load())
        connected = repository.ping(setup=True)
        schema = repository.schema_state()
    except Exception as error:
        raise SystemExit(
            "Live smoke requires a running tutorial ClickHouse instance: "
            f"{type(error).__name__}: {error}"
        ) from error
    if not connected or not all(schema.values()):
        raise SystemExit(
            "Live smoke requires `docker compose up -d` and "
            "`uv run customer-enrichment setup` first."
        )


def execute(mode: str, commands: list[Command]) -> None:
    selected = [command for command in commands if command.mode == mode]
    fingerprint = command_fingerprint(selected)
    start_index = 0
    if mode == "configure" and (ROOT / ".env").exists():
        raise SystemExit("Refusing to overwrite existing .env")
    if mode == "live":
        if os.getenv("CONFIRM_LIVE_SPEND") != "YES" or not os.getenv(
            "PERPLEXITY_API_KEY"
        ):
            raise SystemExit(
                "Live smoke requires CONFIRM_LIVE_SPEND=YES and PERPLEXITY_API_KEY"
            )
        require_live_prerequisites()
        sentinel = ROOT / ".artifacts" / "readme-live-smoke.complete"
        if sentinel.exists():
            raise SystemExit(
                f"Refusing duplicate live smoke; sentinel exists: {sentinel}"
            )
        progress = ROOT / ".artifacts" / "readme-live-smoke.progress.json"
        if progress.exists():
            state = json.loads(progress.read_text())
            if state.get("command_fingerprint") != fingerprint:
                raise SystemExit(
                    "Refusing to resume live smoke because the README command list "
                    f"changed; remove or archive {progress} after reviewing it."
                )
            start_index = int(state["completed_commands"])
            if not 0 <= start_index <= len(selected):
                raise SystemExit(f"Invalid live smoke checkpoint: {progress}")
            print(
                f"Resuming after {start_index} completed live command(s).", flush=True
            )
    for index, command in enumerate(selected[start_index:], start=start_index + 1):
        print(f"[{index}/{len(selected)}] {command.source}", flush=True)
        subprocess.run(
            command.source,
            shell=True,
            executable=SHELL,
            cwd=ROOT,
            check=True,
        )
        if mode == "live":
            progress.parent.mkdir(parents=True, exist_ok=True)
            progress.write_text(
                json.dumps(
                    {
                        "command_fingerprint": fingerprint,
                        "completed_commands": index,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            os.chmod(progress, 0o600)
    if mode == "live":
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(
            json.dumps({"command_fingerprint": fingerprint}, sort_keys=True) + "\n"
        )
        os.chmod(sentinel, 0o600)


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["check", *sorted(MODES)], default="check")
    args = parser.parse_args()
    commands = commands_from_readme()
    validate(commands)
    if args.mode == "check":
        counts = {
            mode: sum(command.mode == mode for command in commands) for mode in MODES
        }
        print(f"Validated {len(commands)} README commands: {counts}")
        return
    execute(args.mode, commands)


if __name__ == "__main__":
    main()
