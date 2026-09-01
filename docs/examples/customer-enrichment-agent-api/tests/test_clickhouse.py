from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from customer_enrichment.clickhouse import ClickHouseRepository
from customer_enrichment.config import Settings
from customer_enrichment.models import EnrichmentRun


def settings() -> Settings:
    return Settings(
        perplexity_api_key=None,
        model="perplexity/glm-5.3",
        confirm_live_spend=False,
        clickhouse_host="localhost",
        clickhouse_http_port=8123,
        clickhouse_native_port=9000,
        clickhouse_database="customer_enrichment",
        clickhouse_setup_user="default",
        clickhouse_app_user="customer_enrichment_app",
        project_root=Path(__file__).resolve().parents[1],
    )


class QueryClient:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def query(self, query, parameters=None):
        self.queries.append((query, parameters or {}))
        return SimpleNamespace(result_rows=self.rows)


def test_get_customer_uses_bound_id_and_returns_only_allowed_fields() -> None:
    secret = "private-note-that-must-not-be-in-sql"
    client = QueryClient(
        [
            [
                "demo-001",
                "Bill Gates",
                "Gates Foundation",
                "Chair, Board Member",
                "Seattle WA",
                "https://example.com/public-profile",
                1,
                datetime.now(timezone.utc),
            ]
        ]
    )
    repository = ClickHouseRepository(settings(), app_client=client)
    customer = repository.get_customer(secret)

    query, parameters = client.queries[0]
    assert secret not in query
    assert "{customer_id:String}" in query
    assert parameters == {"customer_id": secret}
    assert customer is not None
    assert set(customer.tool_payload()) == {
        "customer_id",
        "full_name",
        "company",
        "title",
        "location",
        "known_profile_url",
    }


def test_demo_seed_customers_cover_clear_ambiguous_and_not_found_cases() -> None:
    seed_path = settings().project_root / "data" / "demo_customers.csv"
    with seed_path.open(newline="", encoding="utf-8") as handle:
        records = list(
            csv.DictReader(line for line in handle if not line.startswith("#"))
        )

    assert [record["full_name"] for record in records[:3]] == [
        "Bill Gates",
        "Tim Cook",
        "Mark Zuckerberg",
    ]
    assert all(record["company"] for record in records[:3])
    assert all(record["title"] for record in records[:3])
    assert all(record["location"] for record in records[:3])
    assert all(
        record["known_profile_url"].startswith("https://") for record in records[:3]
    )
    assert records[3]["full_name"] == "Michael Lee"
    assert records[3]["company"] == "Google"
    assert records[3]["title"] == records[3]["location"] == ""
    assert records[4]["full_name"] == "Maren Quill"
    assert records[4]["company"] == "Northstar Quantum Labs"
    assert records[4]["known_profile_url"] == ""


def test_completed_customers_are_skipped_unless_force() -> None:
    client = QueryClient([])
    repository = ClickHouseRepository(settings(), app_client=client)

    repository.select_customers(force=False)
    normal_query = client.queries[-1][0]
    repository.select_customers(force=True)
    forced_query = client.queries[-1][0]

    assert "c.customer_id NOT IN" in normal_query
    assert "c.customer_id NOT IN" not in forced_query
    assert "('matched', 'ambiguous', 'not_found')" in normal_query


class SetupClient:
    def __init__(self) -> None:
        self.ids: set[str] = set()
        self.commands: list[str] = []

    def command(self, statement, parameters=None):
        self.commands.append(statement)
        if statement.strip() == "SELECT 1":
            return 1
        if "DELETE WHERE is_demo = 1" in statement:
            self.ids.clear()
        return None

    def query(self, query, parameters=None):
        if "SELECT customer_id" in query:
            return SimpleNamespace(result_rows=[(item,) for item in sorted(self.ids)])
        raise AssertionError(f"Unexpected query: {query}")

    def insert(self, _table, rows, column_names):
        self.ids.update(row[0] for row in rows)


def test_setup_and_reset_are_idempotent() -> None:
    client = SetupClient()
    repository = ClickHouseRepository(settings(), setup_client=client)

    assert repository.setup() == 5
    repository._setup_client = client
    assert repository.setup() == 0
    repository._setup_client = client
    assert repository.reset() == 5
    assert repository.reset() == 5
    assert len(client.ids) == 5
    reset_statements = [statement for statement in client.commands if "DELETE" in statement]
    assert reset_statements
    assert all("TRUNCATE" not in statement for statement in client.commands)
    assert any("WHERE is_demo = 1" in statement for statement in reset_statements)


def test_limited_user_grants_are_narrow() -> None:
    users_sql = (settings().project_root / "sql" / "users.sql").read_text()
    assert "GRANT SELECT ON customer_enrichment.customers" in users_sql
    assert (
        "GRANT SELECT, INSERT ON customer_enrichment.customer_enrichment_runs"
        in users_sql
    )
    assert "GRANT SELECT ON customer_enrichment.latest_customer_enrichment" in users_sql
    assert "ALTER" not in users_sql
    assert "DROP" not in users_sql


def test_latest_view_uses_run_id_to_break_timestamp_ties() -> None:
    schema_sql = (settings().project_root / "sql" / "schema.sql").read_text()
    assert "CREATE OR REPLACE VIEW" in schema_sql
    assert "tuple(enriched_at, run_id)" in schema_sql
    assert "max(enriched_at) AS latest_enriched_at" in schema_sql
    assert "latest_enriched_at AS enriched_at" in schema_sql


class RunInsertClient:
    def __init__(self) -> None:
        self.count = 0
        self.inserts = []

    def command(self, query, parameters=None):
        assert "SELECT count()" in query
        return self.count

    def insert(self, table, rows, column_names, settings=None):
        self.inserts.append((table, rows, column_names, settings or {}))
        self.count += len(rows)


def test_clickhouse_insert_uses_controller_run_id_as_deduplication_token() -> None:
    client = RunInsertClient()
    repository = ClickHouseRepository(settings(), app_client=client)
    run = EnrichmentRun(
        customer_id="demo-001",
        run_id=uuid4(),
        status="not_found",
        match_explanation="No supported match.",
    )

    assert repository.insert_run(run) is True
    assert client.inserts[0][3] == {
        "insert_deduplication_token": str(run.run_id)
    }
    assert repository.insert_run(run) is False
    assert len(client.inserts) == 1
