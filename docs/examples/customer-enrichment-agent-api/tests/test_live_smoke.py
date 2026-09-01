from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from customer_enrichment.agent import AgentRunner, PerplexityTransport
from customer_enrichment.clickhouse import ClickHouseRepository
from customer_enrichment.config import Settings


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

live_enabled = (
    os.getenv("RUN_LIVE_TESTS") == "1"
    and bool(os.getenv("PERPLEXITY_API_KEY"))
    and os.getenv("CONFIRM_LIVE_SPEND") == "YES"
)


@pytest.mark.live
@pytest.mark.skipif(
    not live_enabled,
    reason="requires RUN_LIVE_TESTS=1, PERPLEXITY_API_KEY, and CONFIRM_LIVE_SPEND=YES",
)
def test_live_people_search_and_clickhouse_insert() -> None:
    settings = Settings.load()
    settings.require_live()
    repository = ClickHouseRepository(settings)
    repository.setup()
    run_id = uuid4()
    try:
        report = AgentRunner(
            repository=repository,
            transport=PerplexityTransport(settings.perplexity_api_key or ""),
            receipt_directory=settings.project_root
            / ".artifacts"
            / "live-test-receipts",
            secrets=(settings.perplexity_api_key or "",),
        ).run_customer(
            customer_id="demo-001",
            model=settings.model,
            run_id=run_id,
        )
        assert report.run.status in {"matched", "ambiguous", "not_found"}
        assert "people_search_results" in report.response_item_types
        assert "get_customer" in report.function_names
        assert "save_customer_enrichment" in report.function_names
        assert report.run.agent_response_ids

        raw_items = json.loads(report.run.raw_people_search_json)
        evidence: dict[str, list[str]] = {}
        for item in raw_items:
            for result in item.get("results", []):
                evidence.setdefault(str(result["id"]), []).append(result["url"])
        if report.run.selected_source_result_id:
            selected_urls = set(evidence[report.run.selected_source_result_id])
            assert len(selected_urls) == 1
            assert selected_urls == {report.run.resolved_profile_url}
        for result_id, url in zip(
            report.run.supporting_source_result_ids,
            report.run.supporting_urls,
            strict=True,
        ):
            supporting_urls = set(evidence[result_id])
            assert len(supporting_urls) == 1
            assert supporting_urls == {url}
        assert repository.run_exists(run_id)
    finally:
        repository.delete_run_for_live_test(run_id)
