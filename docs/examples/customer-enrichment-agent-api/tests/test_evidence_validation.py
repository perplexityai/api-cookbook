from __future__ import annotations

import pytest
from pydantic import ValidationError

from customer_enrichment.evidence import (
    EvidenceValidationError,
    collect_people_search_evidence,
    validate_decision,
)
from customer_enrichment.models import SaveDecision


def _evidence():
    return collect_people_search_evidence(
        [
            {
                "type": "people_search_results",
                "queries": ["Ada Lovelace Analytical Engines"],
                "results": [
                    {
                        "id": 42,
                        "url": "https://example.com/ada",
                        "title": "Ada Lovelace",
                        "snippet": "Public professional profile",
                        "source": "web",
                        "last_updated": "2026-08-01",
                    }
                ],
            }
        ]
    )


def test_matched_requires_selected_result() -> None:
    with pytest.raises(ValidationError, match="requires selected"):
        SaveDecision(
            customer_id="c1",
            status="matched",
            match_explanation="Name and company match.",
        )


def test_fabricated_or_stale_result_id_is_rejected() -> None:
    decision = SaveDecision(
        customer_id="c1",
        status="matched",
        selected_source_result_id="stale",
        match_explanation="Name and company match.",
    )
    with pytest.raises(EvidenceValidationError, match="not returned"):
        validate_decision(decision, current_customer_id="c1", evidence=_evidence())


def test_valid_result_resolves_url_from_evidence_not_model() -> None:
    decision = SaveDecision(
        customer_id="c1",
        status="matched",
        selected_source_result_id="42",
        supporting_source_result_ids=["42"],
        match_explanation="Name and company match.",
    )
    selected_url, urls, snippets = validate_decision(
        decision, current_customer_id="c1", evidence=_evidence()
    )
    assert selected_url == "https://example.com/ada"
    assert urls == ["https://example.com/ada"]
    assert snippets == ["Public professional profile"]


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/profile*",
        "https://example.com/profile`",
        "https://user:password@example.com/profile",
        "javascript:alert(1)",
        "https://example.com/profile with-space",
    ],
)
def test_referenced_invalid_or_markup_tainted_url_is_rejected(url: str) -> None:
    evidence = collect_people_search_evidence(
        [
            {
                "type": "people_search_results",
                "queries": ["Ada Lovelace"],
                "results": [{"id": "bad-url", "url": url}],
            }
        ]
    )
    decision = SaveDecision(
        customer_id="c1",
        status="matched",
        selected_source_result_id="bad-url",
        match_explanation="Name and company match.",
    )

    with pytest.raises(EvidenceValidationError, match="invalid public URL"):
        validate_decision(decision, current_customer_id="c1", evidence=evidence)


def test_conflicting_duplicate_result_id_is_rejected() -> None:
    evidence = collect_people_search_evidence(
        [
            {
                "type": "people_search_results",
                "queries": ["first query"],
                "results": [
                    {"id": 1, "url": "https://example.com/first", "source": "web"}
                ],
            },
            {
                "type": "people_search_results",
                "queries": ["second query"],
                "results": [
                    {"id": 1, "url": "https://example.com/second", "source": "web"}
                ],
            },
        ]
    )
    decision = SaveDecision(
        customer_id="c1",
        status="matched",
        selected_source_result_id="1",
        match_explanation="Name and company match.",
    )

    with pytest.raises(EvidenceValidationError, match="conflicting"):
        validate_decision(decision, current_customer_id="c1", evidence=evidence)
    assert len(evidence.results) == 2
    assert len(evidence.raw_items) == 2


def test_identical_duplicate_result_id_remains_resolvable() -> None:
    item = {
        "type": "people_search_results",
        "queries": ["Ada Lovelace"],
        "results": [
            {
                "id": 42,
                "url": "https://example.com/ada",
                "title": "Ada Lovelace",
                "snippet": "Public professional profile",
                "source": "web",
            }
        ],
    }
    evidence = collect_people_search_evidence([item, item])
    decision = SaveDecision(
        customer_id="c1",
        status="matched",
        selected_source_result_id="42",
        match_explanation="Name and company match.",
    )

    selected_url, _, _ = validate_decision(
        decision, current_customer_id="c1", evidence=evidence
    )
    assert selected_url == "https://example.com/ada"


def test_not_found_cannot_select_or_support_a_profile() -> None:
    with pytest.raises(ValidationError, match="only matched"):
        SaveDecision(
            customer_id="c1",
            status="not_found",
            selected_source_result_id="42",
            match_explanation="No supported match.",
        )
    with pytest.raises(ValidationError, match="cannot contain supporting"):
        SaveDecision(
            customer_id="c1",
            status="not_found",
            supporting_source_result_ids=["42"],
            match_explanation="No supported match.",
        )


@pytest.mark.parametrize("status", ["ambiguous", "not_found"])
def test_non_matched_decisions_cannot_store_profile_fields(status: str) -> None:
    with pytest.raises(ValidationError, match="require null normalized profile fields"):
        SaveDecision(
            customer_id="c1",
            status=status,
            current_company="Invented Company",
            match_explanation="No unique supported match.",
        )


def test_placeholder_text_is_normalized_to_null() -> None:
    decision = SaveDecision(
        customer_id="c1",
        status="ambiguous",
        matched_name="unknown",
        current_title="N/A",
        match_explanation="Two candidates remain.",
    )
    assert decision.matched_name is None
    assert decision.current_title is None
