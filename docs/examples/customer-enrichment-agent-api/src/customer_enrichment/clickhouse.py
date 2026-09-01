from __future__ import annotations

import csv
import time
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from customer_enrichment.config import Settings
from customer_enrichment.models import Customer, EnrichmentRun


TERMINAL_STATUSES = ("matched", "ambiguous", "not_found")


class Repository(Protocol):
    def get_customer(self, customer_id: str) -> Customer | None: ...

    def insert_run(self, run: EnrichmentRun) -> bool: ...


def _split_sql(source: str) -> list[str]:
    lines = [line for line in source.splitlines() if not line.lstrip().startswith("--")]
    return [
        statement.strip()
        for statement in "\n".join(lines).split(";")
        if statement.strip()
    ]


class ClickHouseRepository:
    def __init__(
        self,
        settings: Settings,
        *,
        app_client: Any | None = None,
        setup_client: Any | None = None,
    ) -> None:
        self.settings = settings
        self._app_client = app_client
        self._setup_client = setup_client

    def _client(self, *, setup: bool) -> Any:
        slot = "_setup_client" if setup else "_app_client"
        existing = getattr(self, slot)
        if existing is not None:
            return existing

        import clickhouse_connect

        client = clickhouse_connect.get_client(
            host=self.settings.clickhouse_host,
            port=self.settings.clickhouse_http_port,
            username=(
                self.settings.clickhouse_setup_user
                if setup
                else self.settings.clickhouse_app_user
            ),
            database=("default" if setup else self.settings.clickhouse_database),
        )
        setattr(self, slot, client)
        return client

    def wait_until_ready(self, timeout_seconds: float = 60.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                if self._client(setup=True).command("SELECT 1") == 1:
                    return
            except Exception as error:  # connection exceptions vary by driver
                last_error = error
                self._setup_client = None
            time.sleep(1)
        raise RuntimeError(
            f"ClickHouse was not ready after {timeout_seconds:.0f}s"
        ) from last_error

    def ping(self, *, setup: bool = False) -> bool:
        return self._client(setup=setup).command("SELECT 1") == 1

    def setup(self) -> int:
        self.wait_until_ready()
        client = self._client(setup=True)
        for filename in ("schema.sql", "users.sql"):
            source = (self.settings.project_root / "sql" / filename).read_text()
            source = source.replace(
                "customer_enrichment.", f"{self.settings.clickhouse_database}."
            ).replace(
                "DATABASE IF NOT EXISTS customer_enrichment",
                f"DATABASE IF NOT EXISTS {self.settings.clickhouse_database}",
            )
            source = source.replace(
                "customer_enrichment_app", self.settings.clickhouse_app_user
            )
            for statement in _split_sql(source):
                client.command(statement)
        self._app_client = None
        return self.seed_demo_customers()

    def schema_state(self) -> dict[str, bool]:
        query = """
            SELECT name
            FROM system.tables
            WHERE database = {database:String}
              AND name IN ('customers', 'customer_enrichment_runs', 'latest_customer_enrichment')
        """
        rows = (
            self._client(setup=True)
            .query(query, parameters={"database": self.settings.clickhouse_database})
            .result_rows
        )
        found = {row[0] for row in rows}
        return {
            "customers": "customers" in found,
            "customer_enrichment_runs": "customer_enrichment_runs" in found,
            "latest_customer_enrichment": "latest_customer_enrichment" in found,
        }

    def seed_demo_customers(self) -> int:
        client = self._client(setup=True)
        existing_rows = client.query(
            f"SELECT customer_id FROM {self.settings.clickhouse_database}.customers "
            "WHERE is_demo = {is_demo:UInt8}",
            parameters={"is_demo": 1},
        ).result_rows
        existing = {row[0] for row in existing_rows}

        rows: list[list[Any]] = []
        with (self.settings.project_root / "data" / "demo_customers.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            reader = csv.DictReader(line for line in handle if not line.startswith("#"))
            for record in reader:
                if record["customer_id"] in existing:
                    continue
                rows.append(
                    [
                        record["customer_id"],
                        record["full_name"],
                        record["company"],
                        record["title"] or None,
                        record["location"] or None,
                        record["known_profile_url"] or None,
                        int(record["is_demo"]),
                        datetime.now(timezone.utc),
                    ]
                )
        if rows:
            client.insert(
                f"{self.settings.clickhouse_database}.customers",
                rows,
                column_names=[
                    "customer_id",
                    "full_name",
                    "company",
                    "title",
                    "location",
                    "known_profile_url",
                    "is_demo",
                    "created_at",
                ],
            )
        return len(rows)

    def reset(self) -> int:
        client = self._client(setup=True)
        demo_customer_ids = [
            row[0]
            for row in client.query(
                f"SELECT customer_id FROM {self.settings.clickhouse_database}.customers "
                "WHERE is_demo = {is_demo:UInt8}",
                parameters={"is_demo": 1},
            ).result_rows
        ]
        source = (self.settings.project_root / "sql" / "reset.sql").read_text()
        source = source.replace(
            "customer_enrichment.", f"{self.settings.clickhouse_database}."
        )
        for statement in _split_sql(source):
            client.command(
                statement,
                parameters={"demo_customer_ids": demo_customer_ids},
            )
        return self.seed_demo_customers()

    def get_customer(self, customer_id: str) -> Customer | None:
        query = """
            SELECT customer_id, full_name, company, title, location,
                   known_profile_url, is_demo, created_at
            FROM customers
            WHERE customer_id = {customer_id:String}
            LIMIT 1
        """
        rows = (
            self._client(setup=False)
            .query(query, parameters={"customer_id": customer_id})
            .result_rows
        )
        if not rows:
            return None
        row = rows[0]
        return Customer(
            customer_id=row[0],
            full_name=row[1],
            company=row[2],
            title=row[3],
            location=row[4],
            known_profile_url=row[5],
            is_demo=bool(row[6]),
            created_at=row[7],
        )

    def list_customers(self) -> list[dict[str, Any]]:
        query = """
            SELECT c.customer_id, c.full_name, c.company, c.title, c.location,
                   e.status, e.enriched_at
            FROM customers AS c
            LEFT JOIN latest_customer_enrichment AS e USING (customer_id)
            ORDER BY c.customer_id
        """
        rows = self._client(setup=False).query(query).result_rows
        return [
            {
                "customer_id": row[0],
                "full_name": row[1],
                "company": row[2],
                "title": row[3],
                "location": row[4],
                "status": row[5],
                "enriched_at": row[6],
            }
            for row in rows
        ]

    def select_customers(
        self,
        *,
        limit: int | None = None,
        customer_id: str | None = None,
        force: bool = False,
    ) -> list[Customer]:
        filters: list[str] = []
        parameters: dict[str, Any] = {}
        if customer_id is not None:
            filters.append("c.customer_id = {customer_id:String}")
            parameters["customer_id"] = customer_id
        if not force:
            filters.append(
                "c.customer_id NOT IN "
                "(SELECT customer_id FROM customer_enrichment_runs "
                f"WHERE status IN {TERMINAL_STATUSES})"
            )
        where = " WHERE " + " AND ".join(filters) if filters else ""
        limit_sql = " LIMIT {row_limit:UInt64}" if limit is not None else ""
        if limit is not None:
            parameters["row_limit"] = limit
        query = f"""
            SELECT c.customer_id, c.full_name, c.company, c.title, c.location,
                   c.known_profile_url, c.is_demo, c.created_at
            FROM customers AS c
            {where}
            ORDER BY c.customer_id
            {limit_sql}
        """
        rows = self._client(setup=False).query(query, parameters=parameters).result_rows
        return [
            Customer(
                customer_id=row[0],
                full_name=row[1],
                company=row[2],
                title=row[3],
                location=row[4],
                known_profile_url=row[5],
                is_demo=bool(row[6]),
                created_at=row[7],
            )
            for row in rows
        ]

    def run_exists(self, run_id: UUID) -> bool:
        count = self._client(setup=False).command(
            "SELECT count() FROM customer_enrichment_runs WHERE run_id = {run_id:UUID}",
            parameters={"run_id": run_id},
        )
        return int(count) > 0

    def insert_run(self, run: EnrichmentRun) -> bool:
        if self.run_exists(run.run_id):
            return False
        self._client(setup=False).insert(
            "customer_enrichment_runs",
            [
                [
                    run.customer_id,
                    run.run_id,
                    run.status,
                    run.matched_name,
                    run.current_title,
                    run.current_company,
                    run.location,
                    run.match_explanation,
                    run.selected_source_result_id,
                    run.resolved_profile_url,
                    run.supporting_source_result_ids,
                    run.supporting_urls,
                    run.supporting_snippets,
                    run.people_search_queries,
                    run.raw_people_search_json,
                    run.actual_model,
                    run.agent_response_ids,
                    run.error_category,
                    run.error_message,
                    run.enriched_at,
                ]
            ],
            column_names=list(EnrichmentRun.model_fields),
            settings={"insert_deduplication_token": str(run.run_id)},
        )
        return True

    def list_runs(self, *, customer_id: str | None = None) -> list[dict[str, Any]]:
        where = ""
        parameters: dict[str, Any] = {}
        if customer_id:
            where = "WHERE customer_id = {customer_id:String}"
            parameters["customer_id"] = customer_id
        query = f"""
            SELECT customer_id, run_id, status, matched_name, current_title,
                   current_company, location, match_explanation,
                   selected_source_result_id, resolved_profile_url,
                   supporting_source_result_ids, supporting_urls,
                   people_search_queries, actual_model, agent_response_ids,
                   error_category, error_message, enriched_at
            FROM customer_enrichment_runs
            {where}
            ORDER BY enriched_at DESC
        """
        rows = self._client(setup=False).query(query, parameters=parameters).result_rows
        names = [
            "customer_id",
            "run_id",
            "status",
            "matched_name",
            "current_title",
            "current_company",
            "location",
            "match_explanation",
            "selected_source_result_id",
            "resolved_profile_url",
            "supporting_source_result_ids",
            "supporting_urls",
            "people_search_queries",
            "actual_model",
            "agent_response_ids",
            "error_category",
            "error_message",
            "enriched_at",
        ]
        return [dict(zip(names, row, strict=True)) for row in rows]

    def delete_run_for_live_test(self, run_id: UUID) -> None:
        self._client(setup=True).command(
            f"ALTER TABLE {self.settings.clickhouse_database}.customer_enrichment_runs "
            "DELETE WHERE run_id = {run_id:UUID} SETTINGS mutations_sync = 2",
            parameters={"run_id": run_id},
        )
