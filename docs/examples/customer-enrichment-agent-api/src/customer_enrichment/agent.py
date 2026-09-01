from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import UUID, uuid4

from customer_enrichment.clickhouse import Repository
from customer_enrichment.evidence import (
    as_dict,
    collect_people_search_evidence,
    validate_decision,
)
from customer_enrichment.models import (
    AgentRunReport,
    EnrichmentRun,
    SaveDecision,
    ToolTrace,
)
from customer_enrichment.tools import AGENT_TOOLS, get_customer_tool


MAX_STEPS = 10
MAX_CONTINUATION_TURNS = 10

AGENT_INSTRUCTIONS = """
You enrich exactly one customer using only the three configured tools.

Rules:
1. Call get_customer with the controller-provided customer ID before searching.
2. Start people_search with the person's full name plus company. If ambiguous,
   add the supplied title or location to a second query.
3. Mark matched only when the name and at least one independent identifier agree.
   Prefer company, title, location, or the known public profile URL as that identifier.
4. Mark ambiguous when multiple profiles remain plausible; mark not_found when none
   has enough support. Use null for every field unsupported by People Search evidence.
5. Never infer contact details, handles, professional fields, locations, or URLs from
   memory. Do not contact the person and do not generate outreach.
6. Call save_customer_enrichment once with valid evidence, including for ambiguous and
   not_found. If the controller returns a validation error, correct the arguments and retry;
   after a save is accepted, do not call it again. Cite only result IDs returned by
   people_search in this customer run. Use exactly one selected result for matched and no
   selected result otherwise.
7. Keep match_explanation concise and tie it to source customer fields and evidence.
""".strip()


class AgentTransport(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class PerplexityTransport:
    def __init__(self, api_key: str) -> None:
        from perplexity import Perplexity

        self._client = Perplexity(api_key=api_key, max_retries=0)

    def create(self, **kwargs: Any) -> Any:
        return self._client.responses.create(**kwargs)


class ReceiptWriter:
    def __init__(self, directory: Path, run_id: UUID) -> None:
        self.directory = directory
        self.run_id = run_id

    def write(self, turn: int, response: dict[str, Any]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{self.run_id}.turn-{turn}.json"
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError as error:
            raise FileExistsError(
                f"Refusing to overwrite Agent API receipt: {path}"
            ) from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(response, indent=2, sort_keys=True) + "\n")
        return path


def _response_dict(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if hasattr(response, "to_dict"):
        return response.to_dict(
            mode="json",
            use_api_names=True,
            exclude_unset=True,
            warnings=False,
        )
    if hasattr(response, "model_dump"):
        return response.model_dump(
            mode="json",
            by_alias=True,
            exclude_unset=True,
            warnings=False,
        )
    raise TypeError(f"Unsupported Agent API response type: {type(response).__name__}")


def sanitize_error(error: Exception, secrets: tuple[str, ...] = ()) -> str:
    message = str(error)
    message = re.sub(r"(?i)bearer\s+[^\s,;]+", "Bearer [REDACTED]", message)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message[:500]


class AgentRunner:
    def __init__(
        self,
        *,
        repository: Repository,
        transport: AgentTransport,
        receipt_directory: Path | None = None,
        secrets: tuple[str, ...] = (),
        stage_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.repository = repository
        self.transport = transport
        self.receipt_directory = receipt_directory
        self.secrets = secrets
        self.stage_callback = stage_callback or (lambda _stage: None)

    def run_customer(
        self, *, customer_id: str, model: str, run_id: UUID | None = None
    ) -> AgentRunReport:
        controller_run_id = run_id or uuid4()
        receipt_writer = (
            ReceiptWriter(self.receipt_directory, controller_run_id)
            if self.receipt_directory
            else None
        )
        next_input: str | list[dict[str, Any]] = (
            f"Enrich customer ID {customer_id} and save one decision."
        )
        all_output_items: list[dict[str, Any]] = []
        response_ids: list[str] = []
        response_item_types: list[str] = []
        function_names: list[str] = []
        tool_traces: list[ToolTrace] = []
        actual_model = model
        customer_loaded = False
        evidence_start_index = 0
        pending_run: EnrichmentRun | None = None
        saved_run: EnrichmentRun | None = None
        write_attempted = False
        duplicate_save_attempts = 0
        previous_response_id: str | None = None

        try:
            self.stage_callback("loading")
            for turn in range(1, MAX_CONTINUATION_TURNS + 1):
                request: dict[str, Any] = {
                    "model": model,
                    "instructions": AGENT_INSTRUCTIONS,
                    "tools": AGENT_TOOLS,
                    "input": next_input,
                    "max_steps": MAX_STEPS,
                }
                if previous_response_id is not None:
                    request["previous_response_id"] = previous_response_id
                response = _response_dict(
                    self.transport.create(**request)
                )
                if receipt_writer:
                    receipt_writer.write(turn, response)

                response_id = str(response.get("id") or "")
                if response_id:
                    response_ids.append(response_id)
                actual_model = str(response.get("model") or actual_model)
                status = response.get("status")
                if status != "completed":
                    details = (
                        response.get("incomplete_details")
                        or response.get("error")
                        or {}
                    )
                    if isinstance(details, dict):
                        detail_message = (
                            details.get("message")
                            or details.get("reason")
                            or "no details"
                        )
                    else:
                        detail_message = str(details)
                    raise RuntimeError(
                        f"Agent API response {response_id or '<unknown>'} ended with "
                        f"status {status or '<missing>'}: "
                        f"{detail_message}"
                    )

                output = [as_dict(item) for item in response.get("output") or []]
                all_output_items.extend(output)
                if any(item.get("type") == "people_search_results" for item in output):
                    self.stage_callback("searching")
                for item in output:
                    item_type = str(item.get("type") or "unknown")
                    response_item_types.append(item_type)

                calls = [item for item in output if item.get("type") == "function_call"]
                if not calls:
                    if pending_run is None and saved_run is None:
                        raise RuntimeError(
                            "Agent completed without calling save_customer_enrichment"
                        )
                    if saved_run is None and pending_run is not None:
                        pending_run.actual_model = actual_model
                        pending_run.agent_response_ids = list(response_ids)
                        self.stage_callback("writing")
                        write_attempted = True
                        self.repository.insert_run(pending_run)
                        saved_run = pending_run
                    self.stage_callback("complete")
                    return AgentRunReport(
                        run=saved_run,
                        response_item_types=response_item_types,
                        function_names=function_names,
                        tool_traces=tool_traces,
                        duplicate_save_attempts=duplicate_save_attempts,
                    )

                function_outputs: list[dict[str, Any]] = []
                for call in calls:
                    name = str(call.get("name") or "")
                    function_names.append(name)
                    call_id = str(call.get("call_id") or "")
                    raw_arguments = call.get("arguments") or "{}"
                    arguments: dict[str, Any] = {}
                    started = time.perf_counter()
                    try:
                        arguments = (
                            json.loads(raw_arguments)
                            if isinstance(raw_arguments, str)
                            else dict(raw_arguments)
                        )
                        if name == "get_customer":
                            result = get_customer_tool(
                                self.repository,
                                requested_customer_id=str(
                                    arguments.get("customer_id", "")
                                ),
                                controller_customer_id=customer_id,
                            )
                            if not customer_loaded:
                                customer_loaded = True
                                evidence_start_index = len(all_output_items)
                        elif name == "save_customer_enrichment":
                            self.stage_callback("validating")
                            if pending_run is not None or saved_run is not None:
                                duplicate_save_attempts += 1
                                result = {
                                    "status": "already_accepted",
                                    "run_id": str(controller_run_id),
                                }
                            else:
                                if not customer_loaded:
                                    raise ValueError(
                                        "get_customer must succeed before save_customer_enrichment"
                                    )
                                decision = SaveDecision.model_validate(arguments)
                                evidence = collect_people_search_evidence(
                                    all_output_items[evidence_start_index:]
                                )
                                if not evidence.raw_items:
                                    raise ValueError(
                                        "people_search must run after get_customer before saving"
                                    )
                                selected_url, supporting_urls, supporting_snippets = (
                                    validate_decision(
                                        decision,
                                        current_customer_id=customer_id,
                                        evidence=evidence,
                                    )
                                )
                                pending_run = EnrichmentRun(
                                    customer_id=customer_id,
                                    run_id=controller_run_id,
                                    status=decision.status,
                                    matched_name=decision.matched_name,
                                    current_title=decision.current_title,
                                    current_company=decision.current_company,
                                    location=decision.location,
                                    match_explanation=decision.match_explanation,
                                    selected_source_result_id=(
                                        decision.selected_source_result_id
                                    ),
                                    resolved_profile_url=selected_url,
                                    supporting_source_result_ids=(
                                        decision.supporting_source_result_ids
                                    ),
                                    supporting_urls=supporting_urls,
                                    supporting_snippets=supporting_snippets,
                                    people_search_queries=evidence.queries,
                                    raw_people_search_json=evidence.raw_json(),
                                    actual_model=actual_model,
                                    agent_response_ids=list(response_ids),
                                )
                                result = {
                                    "status": "validated",
                                    "run_id": str(controller_run_id),
                                }
                        else:
                            raise ValueError(f"Unknown custom function: {name}")
                    except Exception as error:
                        if not arguments:
                            arguments = {"invalid": True}
                        result = {
                            "error": True,
                            "category": type(error).__name__,
                            "message": sanitize_error(error, self.secrets),
                        }

                    duration_ms = (time.perf_counter() - started) * 1000
                    tool_traces.append(
                        ToolTrace(
                            name=name,
                            arguments=arguments,
                            result=result,
                            duration_ms=duration_ms,
                        )
                    )
                    function_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "name": name,
                            "output": json.dumps(result, separators=(",", ":")),
                        }
                    )
                if not response_id:
                    raise RuntimeError(
                        "Agent API response ID is required for function continuation"
                    )
                previous_response_id = response_id
                next_input = function_outputs

            raise RuntimeError("Maximum custom-function continuation turns exceeded")
        except Exception as error:
            if write_attempted:
                raise
            error_evidence = collect_people_search_evidence(all_output_items)
            error_run = EnrichmentRun(
                customer_id=customer_id,
                run_id=controller_run_id,
                status="error",
                match_explanation=(
                    "The controller recorded an error after save validation."
                    if pending_run is not None
                    else "The controller recorded an error before a valid save."
                ),
                people_search_queries=error_evidence.queries,
                raw_people_search_json=error_evidence.raw_json(),
                actual_model=actual_model,
                agent_response_ids=response_ids,
                error_category=type(error).__name__,
                error_message=sanitize_error(error, self.secrets),
            )
            self.stage_callback("writing")
            write_attempted = True
            self.repository.insert_run(error_run)
            return AgentRunReport(
                run=error_run,
                response_item_types=response_item_types,
                function_names=function_names,
                tool_traces=tool_traces,
                duplicate_save_attempts=duplicate_save_attempts,
            )
