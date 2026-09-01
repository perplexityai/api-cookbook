from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_MODEL = "perplexity/glm-5.3"


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    perplexity_api_key: str | None
    model: str
    confirm_live_spend: bool
    clickhouse_host: str
    clickhouse_http_port: int
    clickhouse_native_port: int
    clickhouse_database: str
    clickhouse_setup_user: str
    clickhouse_app_user: str
    project_root: Path

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ConfigurationError("MODEL must not be empty")
        identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        for label, value in (
            ("CLICKHOUSE_DATABASE", self.clickhouse_database),
            ("CLICKHOUSE_SETUP_USER", self.clickhouse_setup_user),
            ("CLICKHOUSE_APP_USER", self.clickhouse_app_user),
        ):
            if not identifier.fullmatch(value):
                raise ConfigurationError(
                    f"{label} must be a simple ClickHouse identifier"
                )

    @classmethod
    def load(cls, *, env_file: Path | None = None) -> Settings:
        root = Path(__file__).resolve().parents[2]
        load_dotenv(env_file or root / ".env", override=False)
        return cls(
            perplexity_api_key=os.getenv("PERPLEXITY_API_KEY") or None,
            model=os.getenv("MODEL", DEFAULT_MODEL),
            confirm_live_spend=os.getenv("CONFIRM_LIVE_SPEND", "NO").upper() == "YES",
            clickhouse_host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            clickhouse_http_port=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
            clickhouse_native_port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
            clickhouse_database=os.getenv("CLICKHOUSE_DATABASE", "customer_enrichment"),
            clickhouse_setup_user=os.getenv("CLICKHOUSE_SETUP_USER", "default"),
            clickhouse_app_user=os.getenv(
                "CLICKHOUSE_APP_USER", "customer_enrichment_app"
            ),
            project_root=root,
        )

    def require_live(self) -> None:
        problems: list[str] = []
        if not self.perplexity_api_key:
            problems.append("PERPLEXITY_API_KEY is missing")
        if not self.confirm_live_spend:
            problems.append("CONFIRM_LIVE_SPEND must be YES")
        if problems:
            raise ConfigurationError(
                "; ".join(problems)
                + ". Live Agent API commands spend credits and never use fixtures implicitly."
            )

    def python_is_supported(self) -> bool:
        return sys.version_info[:2] == (3, 12)
