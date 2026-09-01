from __future__ import annotations

import json
from typing import Any, Iterable
from urllib.parse import urlsplit

from customer_enrichment.models import EvidenceBundle, EvidenceResult, SaveDecision


class EvidenceValidationError(ValueError):
    pass


def validate_referenced_url(result_id: str, value: str) -> str:
    url = value.strip()
    parsed = urlsplit(url)
    invalid = (
        url != value
        or parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or any(character.isspace() or ord(character) < 32 for character in url)
        or url.endswith(("*", "`"))
    )
    if invalid:
        raise EvidenceValidationError(
            f"source result ID {result_id} returned an invalid public URL"
        )
    return url


def as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json", by_alias=True)
    raise TypeError(f"Unsupported Agent API item type: {type(item).__name__}")


def collect_people_search_evidence(items: Iterable[Any]) -> EvidenceBundle:
    queries: list[str] = []
    results: list[EvidenceResult] = []
    raw_items: list[dict[str, Any]] = []

    for item in items:
        payload = as_dict(item)
        if payload.get("type") != "people_search_results":
            continue
        raw_items.append(payload)
        for query in payload.get("queries") or []:
            query = str(query).strip()
            if query and query not in queries:
                queries.append(query)
        for raw_result in payload.get("results") or []:
            result = EvidenceResult.model_validate(raw_result)
            results.append(result)

    return EvidenceBundle(
        queries=queries,
        results=results,
        raw_items=raw_items,
    )


def validate_decision(
    decision: SaveDecision, *, current_customer_id: str, evidence: EvidenceBundle
) -> tuple[str | None, list[str], list[str]]:
    if decision.customer_id != current_customer_id:
        raise EvidenceValidationError(
            "save customer_id does not match the controller customer"
        )

    candidates_by_id = evidence.candidates_by_id
    referenced = list(decision.supporting_source_result_ids)
    if decision.selected_source_result_id is not None:
        referenced.append(decision.selected_source_result_id)

    unknown = sorted(
        {result_id for result_id in referenced if result_id not in candidates_by_id}
    )
    if unknown:
        raise EvidenceValidationError(
            "source result IDs were not returned in this run: " + ", ".join(unknown)
        )

    conflicting: list[str] = []
    for result_id in set(referenced):
        payloads = {
            json.dumps(
                result.model_dump(mode="json", by_alias=True, exclude_none=False),
                sort_keys=True,
                separators=(",", ":"),
            )
            for result in candidates_by_id[result_id]
        }
        if len(payloads) > 1:
            conflicting.append(result_id)
    if conflicting:
        raise EvidenceValidationError(
            "source result IDs mapped to conflicting People Search results: "
            + ", ".join(sorted(conflicting))
        )

    available = {
        result_id: candidates[0]
        for result_id, candidates in candidates_by_id.items()
    }

    selected_url = None
    if decision.selected_source_result_id is not None:
        selected_url = validate_referenced_url(
            decision.selected_source_result_id,
            available[decision.selected_source_result_id].url,
        )

    supporting_urls: list[str] = []
    supporting_snippets: list[str] = []
    for result_id in decision.supporting_source_result_ids:
        result = available[result_id]
        supporting_urls.append(validate_referenced_url(result_id, result.url))
        supporting_snippets.append(result.snippet or "")

    return selected_url, supporting_urls, supporting_snippets
