#!/usr/bin/env python3
"""
Competitor Buzz Tracker - a basket of searches and keyword rules becomes a
one-page market-buzz chart (PDF) via two Perplexity Agent API requests:
analytics (sandbox searches the web and counts -> JSON) then chart (sandbox ->
report.pdf, shared with share_file). See the README for details.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from typing import Any, List, Optional, Tuple

import yaml
from pydantic import BaseModel, ConfigDict

from perplexity import Perplexity

from observability import print_costs, print_sandbox_code

POLL_INTERVAL_SECONDS = 4
POLL_TIMEOUT_SECONDS = 900
MAX_STEPS = 10

# A cheaper model handles the mechanical search-and-count; the flagship
# writes the chart code.
ANALYTICS_MODEL = "openai/gpt-5.4"
CHART_MODEL = "openai/gpt-5.5"

ANALYTICS_SYSTEM = """Work in a Python sandbox: search the web, then \
classify and count the results with code. Don't estimate the numbers - \
print the final JSON from the sandbox."""


ANALYTICS_TEMPLATE = """Count how often each brand shows up in current \
phone news.

Search the web for each of these queries, pool the results, and drop \
duplicate URLs:
{query_lines}

Tag each article with these regexes (case-insensitive; an article can \
match several; none -> "Other"):
{keyword_lines}

Return JSON: title "{title}", articles (number of unique articles), and \
series - for each brand and "Other", its total and its share_of_voice \
(its total over the sum of all totals, as a percent rounded to one \
decimal)."""

CHART_SYSTEM = """Work in a Python sandbox with matplotlib (Agg \
backend). Build the chart, save it as report.pdf, and share it with \
share_file."""

CHART_TEMPLATE = """Make a horizontal bar chart from this data.

DATA:
{data_json}

One bar per entry in "series", length = its total, sorted longest \
first, labeled with its total and share_of_voice. Title = the "title" \
field; add a subtitle with the "articles" count and \
"snapshot {snapshot_date}". Keep it clean."""


class Series(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyword: str
    total: int
    share_of_voice: float


class NewsMentions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    articles: int
    series: List[Series]


def load_basket(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def analytics_prompt(basket: dict) -> str:
    keyword_lines = "\n".join(
        f"  - {kw['name']}: {kw['regex']}" for kw in basket["keywords"]
    )
    return ANALYTICS_TEMPLATE.format(
        title=basket["title"],
        query_lines="\n".join(f"  - {q}" for q in basket["queries"]),
        keyword_lines=keyword_lines,
    )


def chart_prompt(data: NewsMentions, snapshot_date: str) -> str:
    return CHART_TEMPLATE.format(
        data_json=data.model_dump_json(indent=2),
        snapshot_date=snapshot_date,
    )


def final_text(response: Any) -> str:
    chunks: List[str] = []
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) != "message":
            continue
        for block in getattr(item, "content", None) or []:
            if getattr(block, "type", None) == "output_text":
                text = getattr(block, "text", None)
                if text:
                    chunks.append(text)
    return "\n\n".join(chunks)


def ran_sandbox(response: Any) -> bool:
    return any(
        getattr(item, "type", None) == "sandbox_results"
        for item in getattr(response, "output", None) or []
    )


def submit_and_wait(client: Perplexity, **create_kwargs: Any) -> Any:
    response = client.responses.create(background=True, **create_kwargs)
    print(f"Submitted response {response.id}; working...", file=sys.stderr)
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while response.status in ("queued", "in_progress"):
        if time.time() > deadline:
            raise TimeoutError("Timed out waiting for the response to finish.")
        time.sleep(POLL_INTERVAL_SECONDS)
        response = client.responses.retrieve(response.id)
    if response.status != "completed":
        raise RuntimeError(f"Request ended with status {response.status!r}.")
    return response


def run_analytics(
    client: Perplexity, basket: dict, model: str
) -> Tuple[NewsMentions, Any]:
    response = submit_and_wait(
        client,
        model=model,
        instructions=ANALYTICS_SYSTEM,
        input=analytics_prompt(basket),
        tools=[{"type": "sandbox"}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "news_mentions",
                "schema": NewsMentions.model_json_schema(),
            },
        },
        max_steps=MAX_STEPS,
    )
    if not ran_sandbox(response):
        raise RuntimeError("Analytics request did not run the sandbox.")
    return NewsMentions.model_validate_json(final_text(response)), response


def run_chart(
    client: Perplexity, data: NewsMentions, snapshot_date: str, model: str
) -> Any:
    return submit_and_wait(
        client,
        model=model,
        instructions=CHART_SYSTEM,
        input=chart_prompt(data, snapshot_date),
        tools=[{"type": "sandbox"}],
        max_steps=MAX_STEPS,
    )


def download_pdf(
    client: Perplexity, response: Any, output: Optional[str]
) -> Optional[str]:
    files = client.responses.files.list(response.id)
    pdf = next(
        (f for f in files.data if f.filename.lower().endswith(".pdf")), None
    )
    if pdf is None:
        names = ", ".join(f.filename for f in files.data) or "(none)"
        print(
            f"No PDF was shared by the sandbox. Files: {names}",
            file=sys.stderr,
        )
        return None

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    out_path = output or f"competitor-buzz-{stamp}.pdf"
    content = client.responses.files.content(pdf.id, response_id=response.id)
    content.write_to_file(out_path)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a one-page market-buzz chart (PDF) from a basket "
            "config, using two Perplexity Agent API requests (analytics, "
            "then chart)."
        )
    )
    parser.add_argument(
        "--config",
        default="basket.yaml",
        help="Path to the basket YAML config (default: basket.yaml).",
    )
    parser.add_argument(
        "--output",
        help=(
            "Output PDF path. Defaults to competitor-buzz-<time>.pdf in the "
            "working directory."
        ),
    )
    parser.add_argument(
        "--show-code",
        action="store_true",
        help="Print the Python the agent wrote and ran in the sandbox.",
    )
    args = parser.parse_args()

    if not os.environ.get("PERPLEXITY_API_KEY"):
        print("Set PERPLEXITY_API_KEY in your environment.", file=sys.stderr)
        return 1

    basket = load_basket(args.config)
    client = Perplexity()

    names = ", ".join(kw["name"] for kw in basket["keywords"])
    snapshot_date = datetime.now().date().isoformat()
    try:
        print(
            f"[1/2] Measuring news buzz for {names}...", file=sys.stderr
        )
        data, analytics_response = run_analytics(
            client, basket, ANALYTICS_MODEL
        )
        parts = [
            f"{s.keyword} {s.total} ({s.share_of_voice}%)"
            for s in data.series
        ]
        print(
            f"      {data.articles} articles - {', '.join(parts)}",
            file=sys.stderr,
        )

        print("[2/2] Rendering the report PDF...", file=sys.stderr)
        chart_response = run_chart(
            client, data, snapshot_date, CHART_MODEL
        )
    except Exception as err:  # noqa: BLE001
        print(f"Error: {err}", file=sys.stderr)
        return 2

    out_path = download_pdf(client, chart_response, args.output)
    if args.show_code:
        print_sandbox_code(analytics_response, "analytics")
        print_sandbox_code(chart_response, "chart")
    print_costs(
        [("Analytics", analytics_response), ("Chart", chart_response)]
    )
    if out_path:
        print(f"\nSaved report to {out_path}", file=sys.stderr)
        return 0
    return 3


if __name__ == "__main__":
    sys.exit(main())
