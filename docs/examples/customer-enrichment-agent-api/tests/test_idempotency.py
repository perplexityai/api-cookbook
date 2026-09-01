from __future__ import annotations

from uuid import uuid4

from customer_enrichment.models import EnrichmentRun


def test_same_controller_run_id_is_idempotent(memory_repository) -> None:
    run_id = uuid4()
    run = EnrichmentRun(
        customer_id="demo-001",
        run_id=run_id,
        status="not_found",
        match_explanation="No supported match.",
    )
    assert memory_repository.insert_run(run) is True
    assert memory_repository.insert_run(run) is False
    assert len(memory_repository.runs) == 1


def test_new_run_id_appends_history(memory_repository) -> None:
    first = EnrichmentRun(
        customer_id="demo-001",
        run_id=uuid4(),
        status="not_found",
        match_explanation="No supported match.",
    )
    second = first.model_copy(update={"run_id": uuid4(), "actual_model": "other/model"})
    assert memory_repository.insert_run(first) is True
    assert memory_repository.insert_run(second) is True
    assert len(memory_repository.runs) == 2
