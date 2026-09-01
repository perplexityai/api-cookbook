from __future__ import annotations

import json
import sys
from typing import Annotated
from uuid import uuid4

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from customer_enrichment.agent import (
    PerplexityTransport,
    ReceiptWriter,
    AgentRunner,
    _response_dict,
    sanitize_error,
)
from customer_enrichment.clickhouse import ClickHouseRepository
from customer_enrichment.config import ConfigurationError, Settings
from customer_enrichment.fixtures import FIXTURE_NAMES, FixtureTransport


app = typer.Typer(
    no_args_is_help=True,
    help="Source-backed customer enrichment with Agent API People Search and ClickHouse.",
)
console = Console()


def _people_search_route_label(fixture: str | None) -> str:
    return "live provider search" if fixture is None else "deterministic fixture response"


def _settings() -> Settings:
    try:
        return Settings.load()
    except Exception as error:
        console.print(f"[red]Configuration error:[/red] {error}")
        raise typer.Exit(2) from error


def _repository(settings: Settings) -> ClickHouseRepository:
    return ClickHouseRepository(settings)


@app.command()
def setup() -> None:
    """Wait for ClickHouse, create schema and grants, and seed demo rows."""
    settings = _settings()
    try:
        inserted = _repository(settings).setup()
    except Exception as error:
        console.print(f"[red]Setup failed:[/red] {escape(sanitize_error(error))}")
        raise typer.Exit(1) from error
    console.print(
        f"[green]ClickHouse is ready.[/green] Added {inserted} missing demo customer(s)."
    )


@app.command()
def customers() -> None:
    """Show source customers and each latest terminal enrichment status."""
    settings = _settings()
    try:
        rows = _repository(settings).list_customers()
    except Exception as error:
        console.print(
            f"[red]ClickHouse query failed:[/red] {escape(sanitize_error(error))}"
        )
        raise typer.Exit(1) from error
    table = Table(title="Source customers")
    for column in ("Customer ID", "Name", "Company", "Title", "Status"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            row["customer_id"],
            row["full_name"],
            row["company"],
            row["title"] or "—",
            row["status"] or "pending",
        )
    console.print(table)


@app.command()
def enrich(
    limit: Annotated[
        int | None, typer.Option(min=1, help="Maximum pending customers to process.")
    ] = None,
    customer_id: Annotated[
        str | None, typer.Option(help="Process only this customer ID.")
    ] = None,
    model: Annotated[
        str | None, typer.Option(help="Override MODEL for this command.")
    ] = None,
    force: Annotated[
        bool, typer.Option(help="Append a new run even after a terminal result.")
    ] = False,
    verbose: Annotated[
        bool, typer.Option(help="Show sanitized tool arguments, IDs, and timings.")
    ] = False,
    fixture: Annotated[
        str | None,
        typer.Option(
            help="Use a deterministic troubleshooting fixture; never proof of live behavior."
        ),
    ] = None,
) -> None:
    """Enrich pending customers; live mode is the default and spends API credits."""
    settings = _settings()
    selected_model = model or settings.model
    if fixture is not None and fixture not in FIXTURE_NAMES:
        console.print(
            f"[red]Unknown fixture.[/red] Choose one of: {', '.join(FIXTURE_NAMES)}"
        )
        raise typer.Exit(2)
    if fixture is None:
        try:
            settings.require_live()
        except ConfigurationError as error:
            console.print(f"[red]Live mode blocked:[/red] {error}")
            raise typer.Exit(2) from error
        if customer_id is None and limit is None:
            console.print(
                "[red]Live mode blocked:[/red] Set --customer-id or --limit to bound API spend."
            )
            raise typer.Exit(2)
    else:
        console.print(
            Panel.fit(
                "FIXTURE MODE — deterministic data, no Agent API call, not live proof",
                style="bold yellow",
            )
        )

    repository = _repository(settings)
    try:
        selected = repository.select_customers(
            limit=limit, customer_id=customer_id, force=force
        )
    except Exception as error:
        console.print(
            f"[red]Could not select customers:[/red] {escape(sanitize_error(error))}"
        )
        raise typer.Exit(1) from error
    if not selected:
        console.print(
            "[green]No pending customers.[/green] Use --force to append another run."
        )
        return

    had_error = False
    for customer in selected:
        console.print(
            f"\n[bold]{customer.customer_id}[/bold] · {customer.full_name} · {customer.company}"
        )
        if fixture:
            transport = FixtureTransport.load(
                settings.project_root, fixture, customer.customer_id
            )
            receipt_directory = None
            secrets: tuple[str, ...] = ()
        else:
            transport = PerplexityTransport(settings.perplexity_api_key or "")
            receipt_directory = settings.project_root / ".artifacts" / "receipts"
            secrets = (settings.perplexity_api_key or "",)

        def show_stage(stage: str) -> None:
            console.print(f"  [cyan]{stage}[/cyan]")

        try:
            report = AgentRunner(
                repository=repository,
                transport=transport,
                receipt_directory=receipt_directory,
                secrets=secrets,
                stage_callback=show_stage,
            ).run_customer(customer_id=customer.customer_id, model=selected_model)
        except Exception as error:
            had_error = True
            console.print(
                f"  [red]controller failure:[/red] "
                f"{escape(sanitize_error(error, secrets))}"
            )
            continue
        run = report.run
        had_error = had_error or run.status == "error"
        console.print(f"  status: [bold]{run.status}[/bold]")
        if run.resolved_profile_url:
            console.print(
                f"  selected profile: {escape(run.current_title or '—')} · "
                f"{escape(run.resolved_profile_url)}"
            )
        console.print(f"  explanation: {escape(run.match_explanation)}")
        raw_evidence_items = json.loads(run.raw_people_search_json)
        candidate_count = sum(
            len(item.get("results") or []) for item in raw_evidence_items
        )
        console.print(
            f"  evidence: {len(run.people_search_queries)} quer{'y' if len(run.people_search_queries) == 1 else 'ies'}, "
            f"{candidate_count} candidate(s)"
        )
        console.print(f"  model: {run.actual_model}")
        console.print(f"  response IDs: {', '.join(run.agent_response_ids) or 'none'}")
        console.print(f"  ClickHouse run ID: {run.run_id}")
        if run.error_message:
            console.print(
                f"  [red]error:[/red] {escape(run.error_category or 'Error')}: "
                f"{escape(run.error_message)}"
            )
        if verbose:
            people_search_route = _people_search_route_label(fixture)
            console.print(
                "  agent tool route: get_customer → bound ClickHouse SELECT; "
                f"people_search → {people_search_route}; save_customer_enrichment → "
                "validated ClickHouse INSERT",
                style="dim",
                markup=False,
            )
            candidate_ids = [
                str(result.get("id"))
                for item in raw_evidence_items
                for result in item.get("results") or []
            ]
            console.print(
                f"  people_search queries={json.dumps(run.people_search_queries)}\n"
                f"    candidate IDs={json.dumps(candidate_ids)}\n"
                f"    validation selected={run.selected_source_result_id!r} "
                f"supporting={run.supporting_source_result_ids} "
                f"resolved_url={run.resolved_profile_url!r}",
                style="dim",
                markup=False,
            )
            for trace in report.tool_traces:
                display_result = trace.result
                if trace.name == "get_customer" and not trace.result.get("error"):
                    display_result = {
                        "customer_id": trace.result.get("customer_id"),
                        "returned_fields": sorted(trace.result),
                    }
                console.print(
                    f"  {trace.name} {trace.duration_ms:.1f} ms\n"
                    f"    args={json.dumps(trace.arguments, sort_keys=True)}\n"
                    f"    result={json.dumps(display_result, sort_keys=True)}",
                    style="dim",
                    markup=False,
                )
            console.print(
                f"  [dim]item types={report.response_item_types}; "
                f"function names={report.function_names}; "
                f"duplicate saves={report.duplicate_save_attempts}[/dim]"
            )
    if had_error:
        raise typer.Exit(1)


@app.command()
def results(
    customer_id: Annotated[
        str | None, typer.Option(help="Filter history to one customer ID.")
    ] = None,
) -> None:
    """Show append-only enrichment history and provenance."""
    settings = _settings()
    try:
        rows = _repository(settings).list_runs(customer_id=customer_id)
    except Exception as error:
        console.print(
            f"[red]ClickHouse query failed:[/red] {escape(sanitize_error(error))}"
        )
        raise typer.Exit(1) from error
    table = Table(title="Enrichment run history")
    for column in (
        "Customer",
        "Status",
        "Model",
        "Source URLs",
        "Source IDs",
        "Queries",
        "Response IDs",
        "Run ID",
        "Enriched at",
    ):
        table.add_column(column)
    for row in rows:
        table.add_row(
            row["customer_id"],
            row["status"],
            row["actual_model"],
            "\n".join(
                ([row["resolved_profile_url"]] if row["resolved_profile_url"] else [])
                + list(row["supporting_urls"])
            )
            or "—",
            "\n".join(
                (
                    [row["selected_source_result_id"]]
                    if row["selected_source_result_id"]
                    else []
                )
                + list(row["supporting_source_result_ids"])
            )
            or "—",
            str(len(row["people_search_queries"])),
            "\n".join(row["agent_response_ids"]) or "—",
            str(row["run_id"]),
            str(row["enriched_at"]),
        )
    console.print(table)


@app.command()
def reset(
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip the interactive confirmation.")
    ] = False,
) -> None:
    """Delete tutorial data and restore the five initial demo customers."""
    if not yes and not typer.confirm(
        "Delete the five demo customers and their enrichment history?"
    ):
        console.print("Reset cancelled.")
        return
    settings = _settings()
    try:
        seeded = _repository(settings).reset()
    except Exception as error:
        console.print(f"[red]Reset failed:[/red] {escape(sanitize_error(error))}")
        raise typer.Exit(1) from error
    console.print(f"[green]Reset complete.[/green] Restored {seeded} demo customers.")


@app.command()
def doctor(
    skip_api: Annotated[
        bool,
        typer.Option(
            help="Run local checks only; skips the billable model availability call."
        ),
    ] = False,
) -> None:
    """Check Python, configuration, ClickHouse, schema, and Agent API access."""
    settings = _settings()
    failures = 0

    def check(label: str, passed: bool, detail: str) -> None:
        nonlocal failures
        failures += 0 if passed else 1
        console.print(
            f"[{'green' if passed else 'red'}]{'PASS' if passed else 'FAIL'}[/] {label}: {detail}"
        )

    check("Python", settings.python_is_supported(), sys.version.split()[0])
    check("Model", bool(settings.model.strip()), settings.model)
    repository = _repository(settings)
    try:
        check("ClickHouse setup connection", repository.ping(setup=True), "SELECT 1")
        schema = repository.schema_state()
        if all(schema.values()):
            check("Schema", True, "customers, runs, and latest view exist")
            check("Limited app connection", repository.ping(setup=False), "SELECT 1")
        else:
            console.print(
                "[yellow]WARN[/yellow] Schema: run `uv run customer-enrichment setup` "
                f"(state: {schema})"
            )
    except Exception as error:
        check("ClickHouse", False, sanitize_error(error))

    if skip_api:
        console.print("[yellow]SKIP[/yellow] Agent API: --skip-api avoids API spend")
    else:
        try:
            settings.require_live()
            run_id = uuid4()
            response = _response_dict(
                PerplexityTransport(settings.perplexity_api_key or "").create(
                    model=settings.model,
                    input="Reply with exactly READY.",
                    max_steps=1,
                    max_output_tokens=256,
                )
            )
            ReceiptWriter(
                settings.project_root / ".artifacts" / "doctor-receipts", run_id
            ).write(1, response)
            passed = response.get("status") == "completed"
            incomplete = response.get("incomplete_details") or {}
            incomplete_reason = (
                incomplete.get("reason")
                if isinstance(incomplete, dict)
                else str(incomplete)
            )
            detail = (
                f"status={response.get('status')}; actual model={response.get('model')}; "
                f"response ID={response.get('id')}"
            )
            if incomplete_reason:
                detail += f"; incomplete reason={incomplete_reason}"
            check(
                "Agent API access/model",
                passed,
                detail,
            )
        except Exception as error:
            check(
                "Agent API access/model",
                False,
                sanitize_error(error, (settings.perplexity_api_key or "",)),
            )
    if failures:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
