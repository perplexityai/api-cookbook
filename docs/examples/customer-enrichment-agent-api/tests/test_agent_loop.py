from __future__ import annotations

import json
import stat
import warnings
from pathlib import Path
from uuid import uuid4

import pytest

from customer_enrichment.agent import AgentRunner, MAX_STEPS, ReceiptWriter, _response_dict
from customer_enrichment.fixtures import FixtureTransport


def test_continuation_loop_handles_both_custom_function_pauses(
    memory_repository,
) -> None:
    transport = FixtureTransport.load(
        Path(__file__).resolve().parents[1],
        "clear_match",
        "demo-001",
    )
    report = AgentRunner(
        repository=memory_repository, transport=transport
    ).run_customer(customer_id="demo-001", model="perplexity/glm-5.3")

    assert report.run.status == "matched"
    assert report.run.agent_response_ids == [
        "resp_fixture_clear_1",
        "resp_fixture_clear_2",
        "resp_fixture_clear_3",
    ]
    assert report.function_names == ["get_customer", "save_customer_enrichment"]
    assert "people_search_results" in report.response_item_types
    assert len(transport.calls) == 3
    assert all(call["max_steps"] == MAX_STEPS for call in transport.calls)
    assert len(transport.calls[0]["tools"]) == 3

    assert transport.calls[0]["input"] == (
        "Enrich customer ID demo-001 and save one decision."
    )
    assert "previous_response_id" not in transport.calls[0]
    assert transport.calls[1]["previous_response_id"] == "resp_fixture_clear_1"
    assert transport.calls[2]["previous_response_id"] == "resp_fixture_clear_2"
    assert [item["type"] for item in transport.calls[1]["input"]] == [
        "function_call_output"
    ]
    assert [item["type"] for item in transport.calls[2]["input"]] == [
        "function_call_output"
    ]
    assert transport.calls[1]["input"][0]["name"] == "get_customer"
    assert transport.calls[2]["input"][0]["name"] == "save_customer_enrichment"


@pytest.mark.parametrize(
    ("fixture_name", "expected_status"),
    [
        ("clear_match", "matched"),
        ("ambiguous", "ambiguous"),
        ("not_found", "not_found"),
    ],
)
def test_terminal_fixtures_are_deterministic(
    memory_repository, fixture_name, expected_status
) -> None:
    transport = FixtureTransport.load(
        Path(__file__).resolve().parents[1], fixture_name, "demo-001"
    )
    report = AgentRunner(
        repository=memory_repository, transport=transport
    ).run_customer(customer_id="demo-001", model="perplexity/glm-5.3")
    assert report.run.status == expected_status
    assert len(memory_repository.runs) == 1


def test_people_results_are_collected_across_response_turns(memory_repository) -> None:
    class SequenceTransport:
        def __init__(self) -> None:
            self.responses = [
                {
                    "id": "r1",
                    "model": "perplexity/glm-5.3",
                    "status": "completed",
                    "output": [
                        {
                            "type": "function_call",
                            "name": "get_customer",
                            "call_id": "g1",
                            "arguments": '{"customer_id":"demo-001"}',
                        }
                    ],
                },
                {
                    "id": "r2",
                    "model": "perplexity/glm-5.3",
                    "status": "completed",
                    "output": [
                        {
                            "type": "people_search_results",
                            "queries": ["Bill Gates Gates Foundation"],
                            "results": [
                                {
                                    "id": 7,
                                    "url": "https://example.com/profile-7",
                                    "title": "Result 7",
                                    "snippet": "Gates Foundation chair",
                                    "source": "web",
                                }
                            ],
                        },
                        {
                            "type": "function_call",
                            "name": "get_customer",
                            "call_id": "g2",
                            "arguments": '{"customer_id":"demo-001"}',
                        },
                    ],
                },
                {
                    "id": "r3",
                    "model": "perplexity/glm-5.3",
                    "status": "completed",
                    "output": [
                        {
                            "type": "people_search_results",
                            "queries": ["Bill Gates Gates Foundation Seattle"],
                            "results": [
                                {
                                    "id": 8,
                                    "url": "https://example.com/profile-8",
                                    "title": "Result 8",
                                    "snippet": "Another candidate",
                                    "source": "web",
                                }
                            ],
                        },
                        {
                            "type": "function_call",
                            "name": "save_customer_enrichment",
                            "call_id": "s1",
                            "arguments": json.dumps(
                                {
                                    "customer_id": "demo-001",
                                    "status": "matched",
                                    "matched_name": "Bill Gates",
                                    "current_title": None,
                                    "current_company": "Gates Foundation",
                                    "location": None,
                                    "selected_source_result_id": "7",
                                    "supporting_source_result_ids": ["8"],
                                    "match_explanation": "Name and company agree.",
                                }
                            ),
                        },
                    ],
                },
                {
                    "id": "r4",
                    "model": "perplexity/glm-5.3",
                    "status": "completed",
                    "output": [{"type": "message", "content": []}],
                },
            ]

        def create(self, **_kwargs):
            return self.responses.pop(0)

    report = AgentRunner(
        repository=memory_repository, transport=SequenceTransport()
    ).run_customer(customer_id="demo-001", model="perplexity/glm-5.3")

    assert report.run.people_search_queries == [
        "Bill Gates Gates Foundation",
        "Bill Gates Gates Foundation Seattle",
    ]
    assert report.run.selected_source_result_id == "7"
    assert report.run.supporting_source_result_ids == ["8"]


def test_invalid_source_fixture_records_error(memory_repository) -> None:
    transport = FixtureTransport.load(
        Path(__file__).resolve().parents[1], "invalid_source_id", "demo-001"
    )
    report = AgentRunner(
        repository=memory_repository, transport=transport
    ).run_customer(customer_id="demo-001", model="perplexity/glm-5.3")

    assert report.run.status == "error"
    assert len(memory_repository.runs) == 1
    save_trace = next(
        trace
        for trace in report.tool_traces
        if trace.name == "save_customer_enrichment"
    )
    assert save_trace.result["category"] == "EvidenceValidationError"


def test_agent_can_correct_a_rejected_markup_tainted_url(memory_repository) -> None:
    transport = FixtureTransport.load(
        Path(__file__).resolve().parents[1],
        "corrected_invalid_url",
        "demo-001",
    )
    report = AgentRunner(
        repository=memory_repository, transport=transport
    ).run_customer(customer_id="demo-001", model="perplexity/glm-5.3")

    save_traces = [
        trace
        for trace in report.tool_traces
        if trace.name == "save_customer_enrichment"
    ]
    assert report.run.status == "matched"
    assert report.run.resolved_profile_url == (
        "https://www.gatesfoundation.org/about/leadership/bill-gates"
    )
    assert report.run.supporting_urls == []
    assert len(transport.calls) == 4
    assert len(save_traces) == 2
    assert save_traces[0].result["category"] == "EvidenceValidationError"
    assert "invalid public URL" in save_traces[0].result["message"]
    assert save_traces[1].result["status"] == "validated"


def test_api_failure_before_save_appends_sanitized_error(memory_repository) -> None:
    transport = FixtureTransport.load(
        Path(__file__).resolve().parents[1], "api_failure", "demo-001"
    )
    report = AgentRunner(
        repository=memory_repository, transport=transport
    ).run_customer(customer_id="demo-001", model="perplexity/glm-5.3")

    assert report.run.status == "error"
    assert report.run.error_category == "RuntimeError"
    assert "simulated" in (report.run.error_message or "")


def test_incomplete_response_after_valid_save_appends_error(memory_repository) -> None:
    transport = FixtureTransport.load(
        Path(__file__).resolve().parents[1], "clear_match", "demo-001"
    )
    transport._responses[-1] = {
        "id": "resp_fixture_incomplete",
        "model": "perplexity/glm-5.3",
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        "output": [],
    }

    report = AgentRunner(
        repository=memory_repository, transport=transport
    ).run_customer(customer_id="demo-001", model="perplexity/glm-5.3")

    assert report.run.status == "error"
    assert report.run.error_category == "RuntimeError"
    assert "incomplete" in (report.run.error_message or "")
    assert "max_output_tokens" in (report.run.error_message or "")
    assert len(memory_repository.runs) == 1


def test_continuation_failure_after_valid_save_appends_error(memory_repository) -> None:
    transport = FixtureTransport.load(
        Path(__file__).resolve().parents[1], "clear_match", "demo-001"
    )
    transport._responses[-1] = {"raise": "continuation timed out"}

    report = AgentRunner(
        repository=memory_repository, transport=transport
    ).run_customer(customer_id="demo-001", model="perplexity/glm-5.3")

    assert report.run.status == "error"
    assert report.run.error_category == "RuntimeError"
    assert "continuation timed out" in (report.run.error_message or "")
    assert report.run.match_explanation.endswith("after save validation.")
    assert len(memory_repository.runs) == 1


def test_duplicate_save_attempt_inserts_only_once(memory_repository) -> None:
    transport = FixtureTransport.load(
        Path(__file__).resolve().parents[1], "duplicate_save", "demo-001"
    )
    report = AgentRunner(
        repository=memory_repository, transport=transport
    ).run_customer(customer_id="demo-001", model="perplexity/glm-5.3")

    assert report.run.status == "matched"
    assert report.duplicate_save_attempts == 1
    assert len(memory_repository.runs) == 1


def test_save_is_rejected_when_people_search_never_ran(memory_repository) -> None:
    class NoSearchTransport:
        def __init__(self):
            self.responses = [
                {
                    "id": "no-search-1",
                    "model": "perplexity/glm-5.3",
                    "status": "completed",
                    "output": [
                        {
                            "type": "function_call",
                            "name": "get_customer",
                            "call_id": "g1",
                            "arguments": '{"customer_id":"demo-001"}',
                        }
                    ],
                },
                {
                    "id": "no-search-2",
                    "model": "perplexity/glm-5.3",
                    "status": "completed",
                    "output": [
                        {
                            "type": "function_call",
                            "name": "save_customer_enrichment",
                            "call_id": "s1",
                            "arguments": json.dumps(
                                {
                                    "customer_id": "demo-001",
                                    "status": "not_found",
                                    "matched_name": None,
                                    "current_title": None,
                                    "current_company": None,
                                    "location": None,
                                    "selected_source_result_id": None,
                                    "supporting_source_result_ids": [],
                                    "match_explanation": "No profile found.",
                                }
                            ),
                        }
                    ],
                },
                {
                    "id": "no-search-3",
                    "model": "perplexity/glm-5.3",
                    "status": "completed",
                    "output": [{"type": "message", "content": []}],
                },
            ]

        def create(self, **_kwargs):
            return self.responses.pop(0)

    report = AgentRunner(
        repository=memory_repository, transport=NoSearchTransport()
    ).run_customer(customer_id="demo-001", model="perplexity/glm-5.3")

    assert report.run.status == "error"
    save_trace = next(
        trace
        for trace in report.tool_traces
        if trace.name == "save_customer_enrichment"
    )
    assert "people_search must run" in save_trace.result["message"]


def test_uncertain_clickhouse_insert_is_not_retried(memory_repository) -> None:
    class FailingRepository(type(memory_repository)):
        def __init__(self):
            super().__init__()
            self.insert_attempts = 0

        def insert_run(self, run):
            self.insert_attempts += 1
            raise RuntimeError("simulated ClickHouse insert timeout")

    repository = FailingRepository()
    transport = FixtureTransport.load(
        Path(__file__).resolve().parents[1], "clear_match", "demo-001"
    )
    with pytest.raises(RuntimeError, match="insert timeout"):
        AgentRunner(repository=repository, transport=transport).run_customer(
            customer_id="demo-001", model="perplexity/glm-5.3"
        )
    assert repository.insert_attempts == 1


def test_receipts_are_private_at_creation_and_never_overwritten(tmp_path) -> None:
    writer = ReceiptWriter(tmp_path / "receipts", uuid4())
    path = writer.write(1, {"id": "response-1", "status": "completed"})
    original = path.read_text()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        writer.write(1, {"id": "response-2", "status": "completed"})
    assert path.read_text() == original


def test_current_sdk_preserves_people_search_items_without_serializer_warnings() -> None:
    from perplexity._models import construct_type
    from perplexity.types.response_create_response import ResponseCreateResponse

    sdk_response = construct_type(
        type_=ResponseCreateResponse,
        value={
            "id": "response-sdk-shape",
            "created_at": 0,
            "model": "perplexity/glm-5.3",
            "object": "response",
            "status": "completed",
            "output": [
                {
                    "type": "people_search_results",
                    "queries": ["Ada Lovelace"],
                    "results": [
                        {
                            "id": 1,
                            "url": "https://example.com/ada",
                            "title": "Ada Lovelace",
                            "snippet": "Public professional profile",
                            "source": "web",
                        }
                    ],
                }
            ],
        },
    )

    with warnings.catch_warnings(record=True) as emitted:
        response = _response_dict(sdk_response)

    assert not emitted
    assert response["output"][0]["type"] == "people_search_results"
    assert response["output"][0]["results"][0]["id"] == 1
