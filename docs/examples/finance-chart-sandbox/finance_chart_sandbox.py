#!/usr/bin/env python3
"""
Finance Chart (Sandbox) - Plot a stock's closing-price history using the
Perplexity Agent API ``sandbox`` tool. The sandbox fetches the prices AND
renders the chart, returning both as files — no local rendering.

Everything runs inside one **background** Agent API request:

  1. The model is given the ``sandbox`` tool — a Python environment with
     ``urllib``/``pandas``/``matplotlib`` and a writable working directory.
  2. It fetches the ticker's daily closing prices from a **pinned** data source
     (Yahoo Finance's v8 chart JSON endpoint), writes them to ``prices.csv``,
     and renders a line chart to ``chart.png``.
  3. Both files are saved to the sandbox workspace, which the Agent API exposes
     as downloadable **artifacts** (``share_file`` output items).

We poll the request to completion, read the shared files off the response, and
download the CSV and PNG. This script has **no third-party dependencies** — it
only speaks raw HTTP.

Why this shape?
- The request uses ``background: true`` and is polled by id so the sandbox run
  can continue if the client disconnects.
- The sandbox creates files. Anything written to the workspace comes back as a
  ``share_file`` output item with a ``file_id``. The script constructs the
  ``/v1/responses/{id}/files/{file_id}/content`` download path; it can also
  discover files via ``GET /v1/responses/{id}/files``.
- **Latency: pin the data source.** The slow part of an unconstrained sandbox
  run is the model *discovering* a working price source (public pages 429 or
  gate behind captchas). Telling it to hit Yahoo's v8 chart JSON endpoint
  directly turns a multi-call hunt into a single fetch, which also leaves token
  budget for rendering the chart in the same session.
- **``finance_search`` has no history.** The top-level ``finance_search`` tool
  returns only the *latest quote* (a single row) on the current deployment — it
  cannot produce a price *series* — so the history is fetched in the sandbox.

The Agent API is called over **raw HTTP** (no SDK) so the request body — and
the sandbox tool in it — is fully visible, and the endpoint is configurable
via ``--base-url`` / ``PERPLEXITY_BASE_URL``.

Docs:
- Agent API:      https://docs.perplexity.ai/docs/agent-api/quickstart
- sandbox:        https://docs.perplexity.ai/docs/agent-api/tools/sandbox
- finance_search: https://docs.perplexity.ai/docs/agent-api/tools/finance-search
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_BASE_URL = "https://api.perplexity.ai"
RESPONSES_PATH = "/v1/responses"

# Filenames the sandbox is told to produce, matched on the way back by suffix.
CSV_NAME = "prices.csv"
PNG_NAME = "chart.png"

# Yahoo's v8 chart JSON understands these range tokens directly; anything else
# is expressed as an explicit period1/period2 window instead.
YAHOO_RANGES = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}


# Friendly --period values mapped to a natural-language phrase (used in logs /
# the chart title). Anything not in this map is passed through verbatim.
PERIOD_PHRASES: Dict[str, str] = {
    "1mo": "the past 1 month",
    "3mo": "the past 3 months",
    "6mo": "the past 6 months",
    "1y": "the past 1 year",
    "2y": "the past 2 years",
    "5y": "the past 5 years",
}


SYSTEM_PROMPT = f"""You run inside a Python sandbox with a writable working
directory that includes `urllib`/`requests`, `pandas`, `matplotlib`, and the
standard library. Your job is to produce two files: a CSV of a stock's daily
closing prices and a line chart of them.

The two files ARE the deliverable. The task is complete only once `{CSV_NAME}`
and `{PNG_NAME}` exist in the working directory — they are returned to the
caller as downloadable artifacts. Do not end your turn with a text answer in
place of the files.

Steps:
1. Fetch the daily closing prices from the EXACT URL you are given (Yahoo
   Finance's v8 chart JSON), sending a browser `User-Agent` header such as
   `Mozilla/5.0`. Parse `result.timestamp` (epoch seconds) together with
   `result.indicators.quote[0].close`; drop any null closes. If that request
   fails or is rate-limited, fall back to the Stooq daily CSV
   (`https://stooq.com/q/d/l/?s=<ticker>.us&i=d`) and filter to the window.
   Never fabricate or interpolate prices.
2. Write the data to `{CSV_NAME}`: header `date,close`; one row per trading
   day; sorted ascending by date; dates YYYY-MM-DD; close as a plain number.
3. Render a closing-price line chart with matplotlib (headless `Agg` backend)
   and save it to `{PNG_NAME}`:
   - figure ~10x5 inches at 150 dpi
   - a single line in color #1f77b4, ~1.6pt wide, with a light fill below it
   - dashed gridlines, x-axis label "Date", y-axis label "Close (USD)"
   - the exact title you are given
   - concise, auto-spaced date ticks on the x-axis
4. Verify both files exist, then print only a one-line confirmation."""


PROMPT_TEMPLATE = (
    "Fetch this exact URL for the daily closing prices: {url}\n"
    "Write {csv} and render {png} for {ticker} over {period_phrase}. "
    'Title the chart exactly "{ticker} closing price — {period_label}".'
)


# ---------------------------------------------------------------------------
# API key + HTTP helpers
# ---------------------------------------------------------------------------
def resolve_api_key(api_key: Optional[str] = None) -> str:
    """Find the Perplexity API key.

    Order: explicit argument, ``PERPLEXITY_API_KEY`` / ``PPLX_API_KEY`` env
    vars, a ``.pplx_api_key`` file, or a ``KEY=value`` line in a local
    ``.env`` (``PERPLEXITY_API_KEY`` or ``PPLX_API_KEY``).
    """
    if api_key:
        return api_key
    for var in ("PERPLEXITY_API_KEY", "PPLX_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    for candidate in (".pplx_api_key", "pplx_api_key"):
        path = Path(candidate)
        if path.exists():
            return path.read_text().strip()
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() in ("PERPLEXITY_API_KEY", "PPLX_API_KEY"):
                return value.strip().strip('"').strip("'")
    raise RuntimeError(
        "API key not found. Set PERPLEXITY_API_KEY, pass --api-key, or add it "
        "to a .pplx_api_key / .env file."
    )


def _request(
    method: str, url: str, key: str, body: Optional[dict], timeout: int
) -> Tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "api-cookbook-finance-chart-sandbox/3.0",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read().decode())
        except Exception:  # noqa: BLE001
            return err.code, {"error": {"message": err.reason}}


def _download(base_url: str, key: str, url_or_path: str, timeout: int = 120) -> bytes:
    """GET a file's raw bytes from an absolute URL or a base-relative path."""
    url = url_or_path if url_or_path.startswith("http") else base_url + url_or_path
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "User-Agent": "api-cookbook-finance-chart-sandbox/3.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _poll(base_url: str, key: str, response_id: str, deadline: float) -> dict:
    """Poll a background response until terminal status (resilient to 5xx)."""
    url = f"{base_url}{RESPONSES_PATH}/{response_id}"
    body: dict = {"status": "in_progress"}
    while body.get("status") in ("queued", "in_progress"):
        if time.time() > deadline:
            raise TimeoutError("Timed out waiting for the sandbox response.")
        time.sleep(3)
        status, body = _request("GET", url, key, None, timeout=60)
        if status >= 500:
            # Transient server error mid-poll — keep waiting.
            body = {"status": "in_progress"}
    return body


def yahoo_chart_url(
    ticker: str, period: str, start: Optional[str], end: Optional[str]
) -> str:
    """Build the Yahoo v8 chart JSON URL for the ticker over the window.

    Uses a ``range`` token for the standard lookback periods; an explicit
    ``period1``/``period2`` epoch window for date ranges or non-standard
    periods.
    """
    base = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}"
    if not start and not end and period in YAHOO_RANGES:
        return f"{base}?range={period}&interval=1d"

    def _epoch(date_str: str) -> int:
        return int(
            datetime.strptime(date_str, "%Y-%m-%d")
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )

    p1 = _epoch(start) if start else 0
    # +1 day so the end date itself is included.
    p2 = _epoch(end) + 86400 if end else int(time.time())
    return f"{base}?period1={p1}&period2={p2}&interval=1d"


def run_sandbox_request(
    base_url: str,
    key: str,
    ticker: str,
    period: str,
    period_label: str,
    period_phrase: str,
    start: Optional[str],
    end: Optional[str],
    model: str,
    max_steps: int,
    poll_timeout: int,
) -> dict:
    """Submit one background Agent API call and poll it to completion."""
    payload = {
        "model": model,
        "instructions": SYSTEM_PROMPT,
        "input": PROMPT_TEMPLATE.format(
            url=yahoo_chart_url(ticker, period, start, end),
            ticker=ticker.upper(),
            period_label=period_label,
            period_phrase=period_phrase,
            csv=CSV_NAME,
            png=PNG_NAME,
        ),
        "tools": [{"type": "sandbox"}],
        "background": True,
        # Headroom: the sandbox spends output tokens writing the code that
        # fetches the data and renders the chart; a tight cap can starve the
        # file-writing step.
        "max_output_tokens": 8192,
        "max_steps": max_steps,
    }
    status, body = _request(
        "POST", f"{base_url}{RESPONSES_PATH}", key, payload, timeout=120
    )
    if status >= 400:
        raise RuntimeError(f"Agent API error {status}: {body.get('error', body)}")
    if not body.get("id"):
        raise RuntimeError(f"Unexpected response (no id): {body}")
    return _poll(base_url, key, body["id"], deadline=time.time() + poll_timeout)


# ---------------------------------------------------------------------------
# Files the sandbox produced
# ---------------------------------------------------------------------------
def shared_files(response: dict, base_url: str, key: str) -> List[Dict[str, str]]:
    """List files the sandbox shared, as ``[{filename, url}]``.

    Prefers ``share_file`` items embedded in the response ``output`` and
    constructs their content paths from ``file_id``. Falls back to
    ``GET /v1/responses/{id}/files``.
    """
    files: List[Dict[str, str]] = []
    response_id = response.get("id")
    if not response_id:
        return files

    for item in response.get("output", []) or []:
        if item.get("type") == "share_file" and item.get("file_id"):
            files.append({
                "filename": item.get("filename", ""),
                "url": (
                    f"{RESPONSES_PATH}/{response_id}/files/"
                    f"{item['file_id']}/content"
                ),
            })
    if files:
        return files

    status, body = _request(
        "GET", f"{base_url}{RESPONSES_PATH}/{response_id}/files", key, None, timeout=60
    )
    if status >= 400:
        return files
    for item in body.get("data", []) or []:
        if item.get("id"):
            files.append({
                "filename": item.get("filename", ""),
                "url": f"{RESPONSES_PATH}/{response_id}/files/{item['id']}/content",
            })
    return files


def pick_file(files: List[Dict[str, str]], suffix: str) -> Optional[Dict[str, str]]:
    """Return the first shared file whose name ends with ``suffix``."""
    for f in files:
        if f.get("filename", "").lower().endswith(suffix):
            return f
    return None


def parse_csv(csv_text: str) -> Tuple[List[datetime], List[float]]:
    """Parse `date,close` CSV text into parallel lists, sorted by date.

    Used to validate the downloaded CSV and report the series length — the
    chart itself is rendered inside the sandbox.
    """
    reader = csv.DictReader(csv_text.splitlines())
    if not reader.fieldnames:
        raise RuntimeError("Empty CSV.")
    cols = {name.strip().lower(): name for name in reader.fieldnames}
    if "date" not in cols or "close" not in cols:
        raise RuntimeError(
            f"CSV missing date/close columns; got {reader.fieldnames}."
        )

    rows: List[Tuple[datetime, float]] = []
    for row in reader:
        raw_date = (row.get(cols["date"]) or "").strip()
        raw_close = (row.get(cols["close"]) or "").strip()
        if not raw_date or not raw_close:
            continue
        try:
            day = datetime.strptime(raw_date[:10], "%Y-%m-%d")
            close = float(raw_close.replace(",", "").replace("$", ""))
        except ValueError:
            continue
        rows.append((day, close))

    if len(rows) < 2:
        raise RuntimeError("Fewer than 2 valid date,close rows parsed.")
    rows.sort(key=lambda r: r[0])
    return [r[0] for r in rows], [r[1] for r in rows]


def sandbox_invocations(response: dict) -> int:
    details = (response.get("usage") or {}).get("tool_calls_details") or {}
    return (details.get("sandbox") or {}).get("invocation", 0) or 0


def total_cost(response: dict) -> Optional[Tuple[float, str]]:
    cost = (response.get("usage") or {}).get("cost")
    if not isinstance(cost, dict) or cost.get("total_cost") is None:
        return None
    return float(cost["total_cost"]), cost.get("currency", "USD")


def build_period_phrase(
    period: Optional[str], start: Optional[str], end: Optional[str]
) -> Tuple[str, str]:
    """Return (period_label, natural-language phrase) for prompts/filenames."""
    if start or end:
        label = f"{start}..{end}"
        if start and end:
            phrase = f"the period from {start} to {end}"
        elif start:
            phrase = f"the period since {start}"
        else:
            phrase = f"the period up to {end}"
        return label, phrase
    period = period or "6mo"
    return period, PERIOD_PHRASES.get(period, f"the past {period}")


def fetch_chart(
    base_url: str,
    key: str,
    ticker: str,
    period: str,
    period_label: str,
    period_phrase: str,
    start: Optional[str],
    end: Optional[str],
    model: str,
    attempts: int,
    max_steps: int,
    poll_timeout: int,
    on_attempt=None,
) -> Tuple[bytes, bytes, List[datetime], dict]:
    """Run up to ``attempts`` background sandbox calls until both files come back.

    Returns ``(csv_bytes, png_bytes, dates, response)``. Raises ``RuntimeError``
    if no attempt yields a downloadable CSV+PNG pair with a usable series.
    ``on_attempt(n, total, note)`` is an optional progress callback (``note`` is
    None at the start of an attempt, or a short failure reason).
    """
    response: dict = {}
    for attempt in range(1, attempts + 1):
        if on_attempt:
            on_attempt(attempt, attempts, None)
        try:
            response = run_sandbox_request(
                base_url, key, ticker, period, period_label, period_phrase,
                start, end, model, max_steps, poll_timeout,
            )
        except (RuntimeError, TimeoutError) as err:
            if on_attempt:
                on_attempt(attempt, attempts, str(err))
            continue

        if response.get("status") == "failed":
            if on_attempt:
                on_attempt(attempt, attempts, f"request failed: {response.get('error')}")
            continue

        files = shared_files(response, base_url, key)
        csv_file = pick_file(files, ".csv")
        png_file = pick_file(files, ".png")
        if not csv_file or not png_file:
            have = ", ".join(f.get("filename", "?") for f in files) or "none"
            if on_attempt:
                on_attempt(attempt, attempts, f"missing CSV/PNG (got: {have})")
            continue

        try:
            csv_bytes = _download(base_url, key, csv_file["url"])
            png_bytes = _download(base_url, key, png_file["url"])
        except (urllib.error.URLError, TimeoutError) as err:
            if on_attempt:
                on_attempt(attempt, attempts, f"download failed: {err}")
            continue

        try:
            dates, _ = parse_csv(csv_bytes.decode("utf-8", "replace"))
        except RuntimeError as err:
            if on_attempt:
                on_attempt(attempt, attempts, f"unusable CSV: {err}")
            continue
        return csv_bytes, png_bytes, dates, response

    raise RuntimeError(
        f"Could not obtain a usable chart from the sandbox after "
        f"{attempts} attempt(s). Sandbox data fetching is best-effort "
        "(third-party sources rate-limit); try more attempts or rerun."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plot a stock's closing-price history using the Perplexity Agent "
            "API sandbox tool (background task). The sandbox fetches the prices "
            "and renders the chart; both come back as downloadable files."
        )
    )
    parser.add_argument("ticker", help="Ticker symbol, e.g. AAPL, MSFT, NVDA.")
    parser.add_argument(
        "--period",
        default="6mo",
        help="Lookback window: 1mo, 3mo, 6mo (default), 1y, 2y, 5y, ...",
    )
    parser.add_argument("--start", help="Start date YYYY-MM-DD (overrides --period).")
    parser.add_argument("--end", help="End date YYYY-MM-DD (use with --start).")
    parser.add_argument("--model", default="openai/gpt-5.5", help="Agent API model.")
    parser.add_argument("--out-dir", default=".", help="Directory for the CSV and PNG.")
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        help="Max background calls to try until the chart comes back "
        "(each is a separate sandbox session). Default 3.",
    )
    parser.add_argument(
        "--max-steps", type=int, default=15, help="Agent max_steps per attempt."
    )
    parser.add_argument(
        "--poll-timeout",
        type=int,
        default=300,
        help="Seconds to poll each background call before giving up.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("PERPLEXITY_BASE_URL", DEFAULT_BASE_URL),
        help="Agent API base URL (or set PERPLEXITY_BASE_URL).",
    )
    parser.add_argument("--api-key", help="Perplexity API key.")
    parser.add_argument(
        "--keep-json", action="store_true", help="Write the raw response JSON."
    )
    args = parser.parse_args()

    try:
        key = resolve_api_key(args.api_key)
    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    ticker = args.ticker.upper()
    period_label, period_phrase = build_period_phrase(
        args.period, args.start, args.end
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = f"{ticker}_{period_label}".replace("..", "_to_")
    csv_path = out_dir / f"{slug}.csv"
    png_path = out_dir / f"{slug}.png"

    def _log(attempt: int, total: int, note: Optional[str]) -> None:
        if note is None:
            print(
                f"[attempt {attempt}/{total}] Asking the sandbox to fetch "
                f"{ticker} closing prices over {period_phrase} and plot them...",
                file=sys.stderr,
            )
        else:
            print(f"  {note}", file=sys.stderr)

    try:
        csv_bytes, png_bytes, dates, response = fetch_chart(
            args.base_url, key, ticker, args.period, period_label, period_phrase,
            args.start, args.end, args.model, args.attempts, args.max_steps,
            args.poll_timeout, on_attempt=_log,
        )
    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 3

    if args.keep_json and response:
        (out_dir / f"{slug}.json").write_text(json.dumps(response, indent=2))

    csv_path.write_bytes(csv_bytes)
    png_path.write_bytes(png_bytes)

    print(f"\nData points: {len(dates)} "
          f"({dates[0]:%Y-%m-%d} → {dates[-1]:%Y-%m-%d})")
    print(f"CSV:   {csv_path}")
    print(f"Chart: {png_path}  (fetched and rendered in the sandbox)")
    print(f"Sandbox invocations: {sandbox_invocations(response)}")
    cost = total_cost(response)
    if cost is not None:
        print(f"Cost: {cost[0]:.4f} {cost[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
