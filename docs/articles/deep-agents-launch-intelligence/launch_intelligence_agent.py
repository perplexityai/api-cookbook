#!/usr/bin/env python3
"""
Product Launch Intelligence Agent
=================================

A Deep-Agents-style multi-agent that produces a structured launch-intelligence
brief on any product, feature, or hardware release. Built on top of the
Perplexity **Agent API** (``client.responses.create``).

Architecture
------------

The cookbook reproduces the Deep Agents pattern (orchestrator + narrowly-scoped
sub-agents + a shared virtual filesystem of workpapers) but every model call is
made through the Perplexity Agent API. There is no Sonar chat-completions
dependency. Each sub-agent is a single Agent API call with its own preset,
instructions, and tool list (``web_search`` + ``fetch_url``). The orchestrator
is also an Agent API call: it receives the four sub-agent summaries plus the
saved workpapers and synthesizes the final brief.

* Sub-agents call the Agent API with ``web_search`` enabled, which performs
  grounded retrieval and returns inline citations the model can quote verbatim.
* The orchestrator runs without web tools — it composes the brief strictly
  from the workpapers the sub-agents wrote, which is what keeps the report
  reproducible and grounded.
* Workpapers live in a Python dict that the script passes between sub-agents,
  exactly mirroring the Deep Agents virtual filesystem semantics.

Run ``python launch_intelligence_agent.py "<launch topic>"`` to use it as a
CLI, or import :func:`investigate_launch` and call it from your own
code/notebook.

Docs:
- Agent API quickstart:  https://docs.perplexity.ai/docs/agent-api/quickstart
- web_search tool:       https://docs.perplexity.ai/docs/agent-api/web-search
- fetch_url tool:        https://docs.perplexity.ai/docs/agent-api/fetch-url
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Cookbook attribution. The Perplexity SDK forwards extra HTTP headers through
# ``default_headers``; ``X-Pplx-Integration`` lets the Perplexity team
# attribute integration traffic.
# ---------------------------------------------------------------------------
COOKBOOK_SLUG = "cookbook/deep-agents-launch-intelligence/0.1.0"
PPLX_INTEGRATION_HEADER = {"X-Pplx-Integration": COOKBOOK_SLUG}

# Default Agent API preset for sub-agents. ``pro-search`` is the recommended
# preset for grounded multi-tool research over the open web.
DEFAULT_SUBAGENT_PRESET = "pro-search"

# The orchestrator does not need web tools — it only synthesizes from
# workpapers — so a lighter preset is fine.
DEFAULT_ORCHESTRATOR_PRESET = "pro-search"


# ---------------------------------------------------------------------------
# Agent API client
# ---------------------------------------------------------------------------
def _build_client(api_key: Optional[str]) -> Any:
    """Construct the Perplexity SDK client with the cookbook attribution slug."""
    try:
        from perplexity import Perplexity
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "perplexityai SDK is required. Install with `pip install perplexityai`."
        ) from exc

    return Perplexity(
        api_key=api_key or os.environ.get("PERPLEXITY_API_KEY"),
        default_headers=PPLX_INTEGRATION_HEADER,
    )


# ---------------------------------------------------------------------------
# Sub-agent prompts. Each sub-agent owns one slice of the brief. Narrow scopes
# are what make the orchestrator's plan reliable.
# ---------------------------------------------------------------------------
ANNOUNCEMENT_PROMPT = """You investigate the official announcement of a product launch.

Your job:
1. Use the web_search and fetch_url tools to find the canonical first-party
   announcement: vendor blog post, press release, keynote recap, spec page,
   or developer changelog. Prefer first-party sources over reblogs.
2. Extract: launch date, headline positioning, named features, supported
   regions or SKUs, pricing and availability windows.
3. Return a Markdown document with two sections:
   - ``## Bullet notes`` — raw extracted facts as bullets, each with a URL.
   - ``## Summary`` — a 6-10 line synthesis with inline citation markers
     ``[1]``, ``[2]`` mapped to the source URLs you actually used.
Never cite a URL that did not appear in your search/fetch results.
"""

RECEPTION_PROMPT = """You investigate independent reception of a product launch:
press coverage, expert reviews, social commentary, and benchmark/quality reports.

Your job:
1. Use web_search and fetch_url to find at least three independent outlets
   (publications, hands-on reviews, analyst notes, developer forums). Avoid
   reblogs of the vendor press release.
2. Capture concrete praise, concrete criticism, and any quantitative benchmarks
   or measurable claims.
3. Return a Markdown document with two sections:
   - ``## Bullet notes`` — raw bullets, each tagged with its source URL.
   - ``## Summary`` — a 6-10 line synthesis with inline citations.
"""

COMPETITOR_PROMPT = """You map the competitive landscape around a product launch.

Your job:
1. Identify 2-4 directly comparable products that ship today (do not invent
   competitors). Use web_search and fetch_url for each.
2. For each competitor capture: vendor, equivalent feature/SKU, pricing if
   public, and one differentiator vs. the launched product.
3. Return a Markdown document with two sections:
   - ``## Bullet notes`` — raw bullets per competitor, each with a URL.
   - ``## Summary`` — a Markdown table with columns: Competitor, Equivalent
     offering, Price, Differentiator. Include inline citations.
"""

RISK_PROMPT = """You assess execution and adoption risks around a product launch.

Your job:
1. Use web_search and fetch_url to find regulatory, security, supply,
   ecosystem, or messaging risks raised by credible sources after the
   announcement.
2. Skip generic boilerplate risks. Each risk you keep must point to a specific
   article, filing, or report.
3. Return a Markdown document with two sections:
   - ``## Bullet notes`` — raw bullets, each with a URL.
   - ``## Summary`` — 3-5 specific risks, each with one sentence of evidence
     and an inline citation.
"""


@dataclass
class SubAgentSpec:
    """A single Deep-Agents-style sub-agent backed by one Agent API call."""

    name: str
    description: str
    prompt: str
    workpaper: str


SUBAGENTS: List[SubAgentSpec] = [
    SubAgentSpec(
        name="announcement-scout",
        description=(
            "Pulls the canonical first-party announcement and headline facts "
            "(launch date, features, pricing, availability)."
        ),
        prompt=ANNOUNCEMENT_PROMPT,
        workpaper="announcement.md",
    ),
    SubAgentSpec(
        name="reception-analyst",
        description=(
            "Surveys independent reception: reviews, press coverage, expert "
            "reactions, and any benchmarks."
        ),
        prompt=RECEPTION_PROMPT,
        workpaper="reception.md",
    ),
    SubAgentSpec(
        name="competitor-mapper",
        description=(
            "Maps 2-4 direct competitors with equivalent SKUs, pricing, and a "
            "single differentiator each."
        ),
        prompt=COMPETITOR_PROMPT,
        workpaper="competitors.md",
    ),
    SubAgentSpec(
        name="risk-auditor",
        description=(
            "Surfaces concrete regulatory, security, supply, ecosystem, or "
            "messaging risks raised by credible sources."
        ),
        prompt=RISK_PROMPT,
        workpaper="risks.md",
    ),
]


# ---------------------------------------------------------------------------
# Orchestrator prompt. The orchestrator only synthesizes from workpapers.
# ---------------------------------------------------------------------------
ORCHESTRATOR_PROMPT = """You are the lead analyst on a product-launch intelligence team.

You are given four workpapers prepared by specialist sub-agents:

- ``announcement.md`` — official launch facts
- ``reception.md`` — independent reception
- ``competitors.md`` — competitive landscape
- ``risks.md`` — execution and adoption risks

Synthesize them into a single brief using exactly this section order:

# <Launch topic> — Launch Intelligence Brief

## 1. Headline
One paragraph: what shipped, when, by whom, at what price.

## 2. Official announcement
Key features and availability, distilled from announcement.md.

## 3. Independent reception
What reviewers and analysts actually said. Quote sparingly, attribute always.

## 4. Competitive landscape
Markdown table from competitors.md.

## 5. Risks and open questions
3-5 specific risks from risks.md.

## 6. Sources
Numbered list of unique URLs cited above.

Hard rules:

* Never cite a URL that did not appear in the workpapers. If a fact is missing
  from the workpapers, omit it rather than guessing.
* Numbers must be attributed (date, source). If a number is not in the
  workpapers, write "not disclosed".
* Keep the final report under ~700 words.

Return only the final report Markdown. Do not call any tools.
"""


# ---------------------------------------------------------------------------
# Agent API call helpers
# ---------------------------------------------------------------------------
def _safe_output_text(response: Any) -> str:
    """Concatenate every assistant text block in an Agent API response.

    The SDK exposes ``response.output_text`` but only when every output item is
    a message; tool-call items break that helper, so walk the list defensively.
    """
    chunks: List[str] = []
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", None) or (
            item.get("type") if isinstance(item, dict) else None
        )
        if item_type != "message":
            continue
        content = (
            getattr(item, "content", None)
            if not isinstance(item, dict)
            else item.get("content")
        )
        for block in content or []:
            block_type = getattr(block, "type", None) or (
                block.get("type") if isinstance(block, dict) else None
            )
            if block_type != "output_text":
                continue
            text = (
                getattr(block, "text", None)
                if not isinstance(block, dict)
                else block.get("text")
            )
            if text:
                chunks.append(text)
    return "\n\n".join(chunks)


def _collect_search_urls(response: Any) -> List[str]:
    """Pull URLs out of ``web_search_results`` items in the Agent API output."""
    urls: List[str] = []
    seen: set[str] = set()
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", None) or (
            item.get("type") if isinstance(item, dict) else None
        )
        if item_type not in ("web_search_results", "fetch_url_results"):
            continue
        nested = (
            getattr(item, "results", None)
            if not isinstance(item, dict)
            else item.get("results", [])
        ) or []
        for r in nested:
            url = (
                getattr(r, "url", None)
                if not isinstance(r, dict)
                else r.get("url")
            )
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


@dataclass
class AgentConfig:
    """Knobs the CLI and ``investigate_launch`` share."""

    subagent_preset: str = DEFAULT_SUBAGENT_PRESET
    orchestrator_preset: str = DEFAULT_ORCHESTRATOR_PRESET
    api_key: Optional[str] = None
    subagent_max_steps: int = 8
    subagent_max_output_tokens: int = 2048
    orchestrator_max_output_tokens: int = 2048


def run_subagent(
    client: Any,
    spec: SubAgentSpec,
    topic: str,
    cfg: AgentConfig,
) -> Tuple[str, List[str]]:
    """Run a single sub-agent through the Agent API.

    Returns ``(workpaper_markdown, source_urls)``.
    """
    user_input = (
        f"Launch topic: {topic}\n\n"
        f"Produce the workpaper described in your instructions."
    )

    response = client.responses.create(
        preset=cfg.subagent_preset,
        instructions=spec.prompt,
        input=user_input,
        tools=[
            {"type": "web_search"},
            {"type": "fetch_url"},
        ],
        max_steps=cfg.subagent_max_steps,
        max_output_tokens=cfg.subagent_max_output_tokens,
    )
    text = _safe_output_text(response)
    urls = _collect_search_urls(response)
    return text, urls


def run_orchestrator(
    client: Any,
    topic: str,
    files: Dict[str, str],
    cfg: AgentConfig,
) -> str:
    """Synthesize the final brief from the sub-agent workpapers."""
    workpaper_blob = "\n\n".join(
        f"--- {name} ---\n{content}" for name, content in files.items()
    )
    user_input = (
        f"Launch topic: {topic}\n\n"
        "Workpapers:\n\n"
        f"{workpaper_blob}\n\n"
        "Write final_report.md following the section order in your "
        "instructions."
    )

    response = client.responses.create(
        preset=cfg.orchestrator_preset,
        instructions=ORCHESTRATOR_PROMPT,
        input=user_input,
        max_output_tokens=cfg.orchestrator_max_output_tokens,
    )
    return _safe_output_text(response)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
@dataclass
class InvestigationResult:
    """Bundles the orchestrator output, raw workpapers, and source URLs."""

    final_report: str
    files: Dict[str, str] = field(default_factory=dict)
    sources: Dict[str, List[str]] = field(default_factory=dict)


def investigate_launch(
    topic: str,
    cfg: Optional[AgentConfig] = None,
    progress: Optional[Callable[[str, float], None]] = None,
) -> InvestigationResult:
    """Run the full pipeline: 4 sub-agents → orchestrator.

    Args:
        topic: Launch to investigate.
        cfg: Tunable knobs (presets, max steps, etc.).
        progress: Optional callback ``(stage_name, elapsed_seconds)`` invoked
            after each sub-agent and the orchestrator finish. Useful for
            CLIs and notebooks that want a live progress line.
    """
    cfg = cfg or AgentConfig()
    client = _build_client(cfg.api_key)

    files: Dict[str, str] = {}
    sources: Dict[str, List[str]] = {}
    started = time.time()

    for spec in SUBAGENTS:
        text, urls = run_subagent(client, spec, topic, cfg)
        files[spec.workpaper] = text
        sources[spec.name] = urls
        if progress:
            progress(spec.name, time.time() - started)

    final_report = run_orchestrator(client, topic, files, cfg)
    files["final_report.md"] = final_report
    if progress:
        progress("orchestrator", time.time() - started)

    return InvestigationResult(
        final_report=final_report,
        files=files,
        sources=sources,
    )


def stream_launch(
    topic: str,
    cfg: Optional[AgentConfig] = None,
) -> Iterable[Tuple[str, float, Dict[str, str]]]:
    """Yield ``(stage_name, elapsed_seconds, files_so_far)`` after each stage.

    Equivalent to ``investigate_launch`` with a progress callback, but exposes
    the partial state at each tick so callers can inspect intermediate
    workpapers.
    """
    cfg = cfg or AgentConfig()
    client = _build_client(cfg.api_key)

    files: Dict[str, str] = {}
    started = time.time()

    for spec in SUBAGENTS:
        text, _urls = run_subagent(client, spec, topic, cfg)
        files[spec.workpaper] = text
        yield spec.name, time.time() - started, dict(files)

    final_report = run_orchestrator(client, topic, files, cfg)
    files["final_report.md"] = final_report
    yield "orchestrator", time.time() - started, dict(files)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_final_report(result: InvestigationResult) -> None:
    if result.final_report:
        print(result.final_report)
        return
    if "final_report.md" in result.files:
        print(result.files["final_report.md"])
        return
    print("(no final_report.md produced)")


def _serialize_result(result: InvestigationResult) -> Dict[str, Any]:
    return {
        "final_report": result.final_report,
        "files": result.files,
        "sources": result.sources,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a launch-intelligence brief with a Deep-Agents-style "
            "multi-agent built on the Perplexity Agent API."
        )
    )
    parser.add_argument(
        "topic",
        help="Launch to investigate, e.g. 'NVIDIA Rubin GPU announcement'.",
    )
    parser.add_argument(
        "--preset",
        default=os.environ.get("PPLX_PRESET", DEFAULT_SUBAGENT_PRESET),
        help=(
            f"Agent API preset for the four sub-agents "
            f"(default: {DEFAULT_SUBAGENT_PRESET})."
        ),
    )
    parser.add_argument(
        "--orchestrator-preset",
        default=os.environ.get(
            "PPLX_ORCHESTRATOR_PRESET", DEFAULT_ORCHESTRATOR_PRESET
        ),
        help=(
            f"Agent API preset for the orchestrator "
            f"(default: {DEFAULT_ORCHESTRATOR_PRESET})."
        ),
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Perplexity API key (defaults to PERPLEXITY_API_KEY env var).",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream sub-agent progress to stderr while the run executes.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full result (workpapers + sources) as JSON.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=8,
        help="Max tool-call steps per sub-agent (default: 8).",
    )
    args = parser.parse_args(argv)

    cfg = AgentConfig(
        subagent_preset=args.preset,
        orchestrator_preset=args.orchestrator_preset,
        api_key=args.api_key,
        subagent_max_steps=args.max_steps,
    )

    if args.stream:
        last: Optional[InvestigationResult] = None
        files_acc: Dict[str, str] = {}
        try:
            for stage, elapsed, files in stream_launch(args.topic, cfg):
                print(f"[{elapsed:6.1f}s] {stage}", file=sys.stderr)
                files_acc = files
            last = InvestigationResult(
                final_report=files_acc.get("final_report.md", ""),
                files=files_acc,
            )
        except Exception as err:  # noqa: BLE001
            print(f"Agent error: {err}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(_serialize_result(last), indent=2, default=str))
        else:
            _print_final_report(last)
        return 0

    started = time.time()

    def _progress(stage: str, elapsed: float) -> None:
        print(f"[{elapsed:6.1f}s] {stage}", file=sys.stderr)

    try:
        result = investigate_launch(args.topic, cfg, progress=_progress)
    except Exception as err:  # noqa: BLE001
        print(f"Agent error: {err}", file=sys.stderr)
        return 2

    print(f"Total elapsed: {time.time() - started:.1f}s", file=sys.stderr)

    if args.json:
        print(json.dumps(_serialize_result(result), indent=2, default=str))
    else:
        _print_final_report(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
