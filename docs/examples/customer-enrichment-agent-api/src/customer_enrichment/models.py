from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TerminalStatus = Literal["matched", "ambiguous", "not_found"]
RunStatus = Literal["matched", "ambiguous", "not_found", "error"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def nullable_text(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.lower() in {"", "unknown", "n/a", "none", "null"}:
            return None
        return cleaned
    return value


class Customer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    full_name: str
    company: str
    title: str | None = None
    location: str | None = None
    known_profile_url: str | None = None
    is_demo: bool = True
    created_at: datetime = Field(default_factory=utc_now)

    _normalize_optional = field_validator(
        "title", "location", "known_profile_url", mode="before"
    )(nullable_text)

    def tool_payload(self) -> dict[str, Any]:
        """Return only fields explicitly allowed to leave ClickHouse."""
        return self.model_dump(
            include={
                "customer_id",
                "full_name",
                "company",
                "title",
                "location",
                "known_profile_url",
            }
        )


class EvidenceResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    result_id: str = Field(alias="id")
    url: str = Field(min_length=1)
    title: str | None = None
    snippet: str | None = None
    source: str | None = None
    last_updated: str | None = None

    @field_validator("result_id", mode="before")
    @classmethod
    def stringify_id(cls, value: Any) -> str:
        if value is None or str(value).strip() == "":
            raise ValueError("People Search result ID must not be empty")
        return str(value)

    _normalize_optional = field_validator(
        "title", "snippet", "source", "last_updated", mode="before"
    )(nullable_text)


class EvidenceBundle(BaseModel):
    queries: list[str] = Field(default_factory=list)
    results: list[EvidenceResult] = Field(default_factory=list)
    raw_items: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def candidates_by_id(self) -> dict[str, list[EvidenceResult]]:
        grouped: dict[str, list[EvidenceResult]] = {}
        for result in self.results:
            grouped.setdefault(result.result_id, []).append(result)
        return grouped

    def raw_json(self) -> str:
        return json.dumps(self.raw_items, sort_keys=True, separators=(",", ":"))


class SaveDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    status: TerminalStatus
    matched_name: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    selected_source_result_id: str | None = None
    supporting_source_result_ids: list[str] = Field(default_factory=list)
    match_explanation: str = Field(min_length=1, max_length=600)

    _normalize_optional = field_validator(
        "matched_name",
        "current_title",
        "current_company",
        "location",
        "selected_source_result_id",
        mode="before",
    )(nullable_text)

    @field_validator("selected_source_result_id", mode="before")
    @classmethod
    def stringify_selected_id(cls, value: Any) -> Any:
        value = nullable_text(value)
        return None if value is None else str(value)

    @field_validator("supporting_source_result_ids", mode="before")
    @classmethod
    def stringify_supporting_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [str(item) for item in value]

    @model_validator(mode="after")
    def validate_status_shape(self) -> SaveDecision:
        if self.status == "matched" and self.selected_source_result_id is None:
            raise ValueError("matched status requires selected_source_result_id")
        if self.status != "matched" and self.selected_source_result_id is not None:
            raise ValueError("only matched status may select a profile result")
        normalized_fields = (
            self.matched_name,
            self.current_title,
            self.current_company,
            self.location,
        )
        if self.status != "matched" and any(
            value is not None for value in normalized_fields
        ):
            raise ValueError(
                "ambiguous and not_found statuses require null normalized profile fields"
            )
        if self.status == "not_found" and self.supporting_source_result_ids:
            raise ValueError("not_found cannot contain supporting source results")
        return self


class EnrichmentRun(BaseModel):
    customer_id: str
    run_id: UUID
    status: RunStatus
    matched_name: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    match_explanation: str = ""
    selected_source_result_id: str | None = None
    resolved_profile_url: str | None = None
    supporting_source_result_ids: list[str] = Field(default_factory=list)
    supporting_urls: list[str] = Field(default_factory=list)
    supporting_snippets: list[str] = Field(default_factory=list)
    people_search_queries: list[str] = Field(default_factory=list)
    raw_people_search_json: str = "[]"
    actual_model: str = ""
    agent_response_ids: list[str] = Field(default_factory=list)
    error_category: str | None = None
    error_message: str | None = None
    enriched_at: datetime = Field(default_factory=utc_now)


class ToolTrace(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    duration_ms: float


class AgentRunReport(BaseModel):
    run: EnrichmentRun
    response_item_types: list[str] = Field(default_factory=list)
    function_names: list[str] = Field(default_factory=list)
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    duplicate_save_attempts: int = 0
