from __future__ import annotations

from typing import Any

from customer_enrichment.clickhouse import Repository


PEOPLE_SEARCH_TOOL: dict[str, Any] = {
    "type": "people_search",
    "max_tokens": 10_000,
    "max_tokens_per_page": 1_000,
}

GET_CUSTOMER_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "get_customer",
    "description": (
        "Load the minimum public identifying fields for exactly one customer. "
        "Call this before people_search."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "The controller-provided customer ID.",
            }
        },
        "required": ["customer_id"],
        "additionalProperties": False,
    },
}

SAVE_ENRICHMENT_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "save_customer_enrichment",
    "description": (
        "Save exactly one evidence-based match decision. Submit People Search result "
        "IDs only; the application resolves trusted URLs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["matched", "ambiguous", "not_found"],
            },
            "matched_name": {"type": ["string", "null"]},
            "current_title": {"type": ["string", "null"]},
            "current_company": {"type": ["string", "null"]},
            "location": {"type": ["string", "null"]},
            "selected_source_result_id": {"type": ["string", "integer", "null"]},
            "supporting_source_result_ids": {
                "type": "array",
                "items": {"type": ["string", "integer"]},
            },
            "match_explanation": {"type": "string", "maxLength": 600},
        },
        "required": [
            "customer_id",
            "status",
            "matched_name",
            "current_title",
            "current_company",
            "location",
            "selected_source_result_id",
            "supporting_source_result_ids",
            "match_explanation",
        ],
        "additionalProperties": False,
    },
}

AGENT_TOOLS = [PEOPLE_SEARCH_TOOL, GET_CUSTOMER_TOOL, SAVE_ENRICHMENT_TOOL]


def get_customer_tool(
    repository: Repository, *, requested_customer_id: str, controller_customer_id: str
) -> dict[str, Any]:
    if requested_customer_id != controller_customer_id:
        raise ValueError(
            "get_customer customer_id does not match the controller customer"
        )
    customer = repository.get_customer(requested_customer_id)
    if customer is None:
        raise LookupError("customer not found")
    return customer.tool_payload()
