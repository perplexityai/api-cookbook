from __future__ import annotations

from typer.testing import CliRunner

from customer_enrichment import cli


class HealthyRepository:
    def ping(self, *, setup=False):
        return True

    def schema_state(self):
        return {
            "customers": True,
            "customer_enrichment_runs": True,
            "latest_customer_enrichment": True,
        }


def test_cli_output_never_contains_configured_secret(monkeypatch) -> None:
    secret = "TOP_SECRET_SENTINEL_NEVER_PRINT"
    monkeypatch.setenv("PERPLEXITY_API_KEY", secret)
    monkeypatch.setattr(cli, "_repository", lambda _settings: HealthyRepository())

    result = CliRunner().invoke(cli.app, ["doctor", "--skip-api"])

    assert result.exit_code == 0
    assert secret not in result.stdout


def test_fixture_mode_is_conspicuously_labeled(monkeypatch) -> None:
    class EmptyRepository:
        def select_customers(self, **_kwargs):
            return []

    monkeypatch.setattr(cli, "_repository", lambda _settings: EmptyRepository())
    result = CliRunner().invoke(cli.app, ["enrich", "--fixture", "clear_match"])
    assert result.exit_code == 0
    assert "FIXTURE MODE" in result.stdout
    assert "not live proof" in result.stdout


def test_people_search_route_label_distinguishes_fixture_from_live() -> None:
    assert cli._people_search_route_label(None) == "live provider search"
    assert (
        cli._people_search_route_label("clear_match")
        == "deterministic fixture response"
    )


def test_live_enrichment_requires_a_bounded_customer_count(monkeypatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "TOP_SECRET_SENTINEL")
    monkeypatch.setenv("CONFIRM_LIVE_SPEND", "YES")
    result = CliRunner().invoke(cli.app, ["enrich"])
    assert result.exit_code == 2
    assert "--customer-id or --limit" in result.stdout


def test_doctor_reports_incomplete_reason_and_uses_viable_budget(monkeypatch) -> None:
    class IncompleteTransport:
        def __init__(self) -> None:
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            return {
                "id": "response-incomplete",
                "model": "perplexity/glm-5.3",
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [],
            }

    class NoopReceiptWriter:
        def write(self, *_args, **_kwargs):
            return None

    transport = IncompleteTransport()
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("CONFIRM_LIVE_SPEND", "YES")
    monkeypatch.setattr(cli, "_repository", lambda _settings: HealthyRepository())
    monkeypatch.setattr(cli, "PerplexityTransport", lambda _key: transport)
    monkeypatch.setattr(cli, "ReceiptWriter", lambda *_args: NoopReceiptWriter())

    result = CliRunner().invoke(cli.app, ["doctor"])

    assert result.exit_code == 1
    assert "status=incomplete" in result.stdout
    assert "incomplete reason=max_output_tokens" in result.stdout
    assert transport.kwargs["max_output_tokens"] == 256
