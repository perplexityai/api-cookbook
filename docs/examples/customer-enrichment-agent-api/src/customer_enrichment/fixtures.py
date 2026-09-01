from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_NAMES = (
    "clear_match",
    "ambiguous",
    "not_found",
    "invalid_source_id",
    "corrected_invalid_url",
    "api_failure",
    "duplicate_save",
)


class FixtureTransport:
    def __init__(self, fixture_path: Path, customer_id: str) -> None:
        source = fixture_path.read_text().replace("__CUSTOMER_ID__", customer_id)
        self._responses = json.loads(source)
        self.calls: list[dict[str, Any]] = []

    @classmethod
    def load(cls, project_root: Path, name: str, customer_id: str) -> FixtureTransport:
        if name not in FIXTURE_NAMES:
            raise ValueError(
                f"Unknown fixture {name!r}; choose one of {', '.join(FIXTURE_NAMES)}"
            )
        return cls(project_root / "tests" / "fixtures" / f"{name}.json", customer_id)

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if not self._responses:
            raise RuntimeError("Fixture response sequence exhausted")
        response = self._responses.pop(0)
        if "raise" in response:
            raise RuntimeError(response["raise"])
        return response
