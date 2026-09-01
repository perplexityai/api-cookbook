from __future__ import annotations

from uuid import UUID

import pytest

from customer_enrichment.models import Customer, EnrichmentRun


class MemoryRepository:
    def __init__(self, customer: Customer | None = None) -> None:
        self.customer = customer or Customer(
            customer_id="demo-001",
            full_name="Bill Gates",
            company="Gates Foundation",
            title="Chair, Board Member",
            location="Seattle WA",
            known_profile_url=(
                "https://www.gatesfoundation.org/about/leadership/bill-gates"
            ),
        )
        self.runs: list[EnrichmentRun] = []

    def get_customer(self, customer_id: str) -> Customer | None:
        return self.customer if customer_id == self.customer.customer_id else None

    def insert_run(self, run: EnrichmentRun) -> bool:
        if any(existing.run_id == run.run_id for existing in self.runs):
            return False
        self.runs.append(run)
        return True

    def run_exists(self, run_id: UUID) -> bool:
        return any(run.run_id == run_id for run in self.runs)


@pytest.fixture
def memory_repository() -> MemoryRepository:
    return MemoryRepository()
