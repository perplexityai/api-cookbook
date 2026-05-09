#!/usr/bin/env python3
"""
Product Launch Intelligence Agent
=================================

A LangChain Deep Agent that produces a structured launch-intelligence brief on
any product, feature, or hardware release. Built on:

* ``deepagents.create_deep_agent`` for orchestration, planning, sub-agents,
  and a virtual filesystem (workpapers).
* The Perplexity Search API (via the official ``perplexityai`` Python SDK)
  for grounded web search with citations.
* ``langchain-perplexity`` for the chat model that powers each agent.

This is a Perplexity-native take on the Deep Agents pattern. The orchestrator
delegates focused queries to specialist sub-agents, each of which calls the
Perplexity Search API directly, drops findings into named workpaper files, and
returns a citation-rich summary back to the orchestrator. The final report is
synthesized from those workpapers — never invented from the model's parametric
memory.

Run ``python launch_intelligence_agent.py "<launch topic>"`` to use it as a CLI,
or import :func:`investigate_launch` and call it from your own code/notebook.

Docs:
- Perplexity Search API:  https://docs.perplexity.ai/docs/search-api
- LangChain Perplexity:   https://python.langchain.com/docs/integrations/chat/perplexity
- deepagents:             https://github.com/langchain-ai/deepagents
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Cookbook attribution. The Perplexity SDK forwards extra HTTP headers through
# ``default_headers``; ``X-Pplx-Integration`` lets the API team identify
# integration traffic. For the LangChain chat model we cannot easily inject
# request headers, so attribution is best-effort.
# ---------------------------------------------------------------------------
COOKBOOK_SLUG = "cookbook/deep-agents-launch-intelligence/0.1.0"
PPLX_INTEGRATION_HEADER = {"X-Pplx-Integration": COOKBOOK_SLUG}

# Default Perplexity chat model surfaced through ``langchain-perplexity``.
# Override with --model or PPLX_MODEL.
DEFAULT_MODEL = "sonar-pro"


# ---------------------------------------------------------------------------
# Perplexity Search API tool (the only "external" tool the sub-agents use)
# ---------------------------------------------------------------------------
def _build_search_client(api_key: Optional[str]) -> Any:
    """Construct an SDK client targeting the Perplexity Search API."""
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


def _format_search_results(payload: Any) -> str:
    """Render Perplexity Search API results as a citation-friendly Markdown list.

    The Search API returns one result list per submitted query. We flatten and
    de-duplicate so the model sees a single set of (title, url, snippet)
    triples. The agent should cite the exact URLs returned here rather than
    inventing links.
    """
    results: List[Dict[str, Any]] = []
    raw_results = (
        payload.get("results") if isinstance(payload, dict) else getattr(payload, "results", [])
    ) or []
    for item in raw_results:
        if not isinstance(item, dict):
            item = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        results.append(item)

    seen: set[str] = set()
    lines: List[str] = []
    for r in results:
        url = r.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        title = r.get("title") or url
        snippet = r.get("snippet") or r.get("content") or ""
        date = r.get("date") or ""
        meta = f" ({date})" if date else ""
        lines.append(f"- **{title}**{meta}\n  {url}\n  {snippet.strip()}")
    if not lines:
        return "No results returned by Perplexity Search."
    return "\n".join(lines)


def make_perplexity_search_tool(api_key: Optional[str] = None) -> Any:
    """Return a LangChain ``@tool`` wrapping ``client.search.create``.

    The Perplexity Search API accepts up to five queries in a single call,
    which the agents exploit to fan out related searches cheaply. We expose
    that as the tool's ``queries`` argument.
    """
    from langchain_core.tools import tool

    client = _build_search_client(api_key)

    @tool("perplexity_search", return_direct=False)
    def perplexity_search(
        queries: List[str],
        max_results: int = 8,
        max_tokens_per_page: int = 512,
    ) -> str:
        """Run one or more grounded web searches via the Perplexity Search API.

        Args:
            queries: 1-5 short, focused web queries. Phrase each like a search
                bar query, not a chat message.
            max_results: Total results to keep across all queries (1-20).
            max_tokens_per_page: Per-page snippet budget. Lower is faster.

        Returns:
            A Markdown bullet list of unique (title, url, snippet) results.
            The agent MUST cite the URLs exactly as returned.
        """
        if not queries:
            return "No queries provided."
        # Cap to API limits.
        queries = [q.strip() for q in queries if q and q.strip()][:5]
        max_results = max(1, min(int(max_results), 20))
        max_tokens_per_page = max(64, min(int(max_tokens_per_page), 1024))

        response = client.search.create(
            query=queries,
            max_results=max_results,
            max_tokens_per_page=max_tokens_per_page,
        )
        return _format_search_results(response)

    return perplexity_search


# ---------------------------------------------------------------------------
# Sub-agent prompts. Each sub-agent owns one slice of the brief. Keeping the
# prompts narrow is what makes the orchestrator's plan reliable.
# ---------------------------------------------------------------------------
ANNOUNCEMENT_PROMPT = """You investigate the official announcement of a
product launch.

Your job:
1. Use ``perplexity_search`` (run up to 5 queries) to find the canonical first-
   party announcement: vendor blog post, press release, keynote recap, spec
   page, or developer changelog. Prefer first-party sources over reblogs.
2. Extract: launch date, headline positioning, named features, supported
   regions or SKUs, pricing and availability windows.
3. Save the raw bullet notes to ``announcement.md`` using ``write_file``.
4. Return a 6-10 line summary back to the orchestrator with inline citation
   markers like [1], [2] mapped to the source URLs you used. Never cite a URL
   that did not appear in the search tool output.
"""

RECEPTION_PROMPT = """You investigate independent reception of a product launch:
press coverage, expert reviews, social commentary, and benchmark/quality
reports.

Your job:
1. Use ``perplexity_search`` to find at least three independent outlets
   (publications, hands-on reviews, analyst notes, developer forums). Avoid
   reblogs of the vendor press release.
2. Capture concrete praise, concrete criticism, and any quantitative
   benchmarks or measurable claims.
3. Save the raw bullet notes to ``reception.md``.
4. Return a 6-10 line synthesis to the orchestrator with inline citations
   ([1], [2], ...) mapped to the URLs you actually used.
"""

COMPETITOR_PROMPT = """You map the competitive landscape around a product
launch.

Your job:
1. Identify 2-4 directly comparable products that ship today (do not invent
   competitors). Use ``perplexity_search`` for each.
2. For each competitor capture: vendor, equivalent feature/SKU, pricing if
   public, and one differentiator vs. the launched product.
3. Save the raw bullet notes to ``competitors.md``.
4. Return a Markdown table to the orchestrator with columns: Competitor,
   Equivalent offering, Price, Differentiator. Include inline citations.
"""

RISK_PROMPT = """You assess execution and adoption risks around a product
launch.

Your job:
1. Use ``perplexity_search`` to find regulatory, security, supply, ecosystem,
   or messaging risks raised by credible sources after the announcement.
2. Skip generic boilerplate risks. Each risk you keep must point to a specific
   article, filing, or report.
3. Save the raw bullet notes to ``risks.md``.
4. Return 3-5 specific risks to the orchestrator, each with one sentence of
   evidence and an inline citation.
"""


SUBAGENTS: List[Dict[str, Any]] = [
    {
        "name": "announcement-scout",
        "description": (
            "Pulls the canonical first-party announcement and headline facts "
            "(launch date, features, pricing, availability)."
        ),
        "prompt": ANNOUNCEMENT_PROMPT,
    },
    {
        "name": "reception-analyst",
        "description": (
            "Surveys independent reception: reviews, press coverage, expert "
            "reactions, and any benchmarks."
        ),
        "prompt": RECEPTION_PROMPT,
    },
    {
        "name": "competitor-mapper",
        "description": (
            "Maps 2-4 direct competitors with equivalent SKUs, pricing, and a "
            "single differentiator each."
        ),
        "prompt": COMPETITOR_PROMPT,
    },
    {
        "name": "risk-auditor",
        "description": (
            "Surfaces concrete regulatory, security, supply, ecosystem, or "
            "messaging risks raised by credible sources."
        ),
        "prompt": RISK_PROMPT,
    },
]


# ---------------------------------------------------------------------------
# Orchestrator prompt
# ---------------------------------------------------------------------------
ORCHESTRATOR_PROMPT = """You are the lead analyst on a product-launch
intelligence team. You coordinate four specialist sub-agents and produce one
final brief.

Operating procedure:

1. Read the user's launch topic. If it is ambiguous, pick the most likely
   recent launch and proceed — do not stall asking for clarification.
2. Plan the work using the planning tool. The standard plan is:
   a. Delegate to ``announcement-scout`` to capture official launch facts.
   b. Delegate to ``reception-analyst`` for independent coverage.
   c. Delegate to ``competitor-mapper`` for the comparable landscape.
   d. Delegate to ``risk-auditor`` for execution and adoption risks.
3. Each sub-agent writes its raw notes to a workpaper file
   (``announcement.md``, ``reception.md``, ``competitors.md``, ``risks.md``)
   and returns a short citation-rich summary to you.
4. Read the workpapers back with ``read_file`` if you need detail beyond the
   summaries.
5. Synthesize the final report into ``final_report.md`` using ``write_file``.
   Use this exact section order:

   # <Launch topic> — Launch Intelligence Brief

   ## 1. Headline
   One paragraph: what shipped, when, by whom, at what price.

   ## 2. Official announcement
   Key features and availability, distilled from announcement.md.

   ## 3. Independent reception
   What reviewers and analysts actually said. Quote sparingly, attribute
   always.

   ## 4. Competitive landscape
   Markdown table from competitors.md.

   ## 5. Risks and open questions
   3-5 specific risks from risks.md.

   ## 6. Sources
   Numbered list of unique URLs cited above. Use only URLs that appeared in
   the sub-agents' summaries or workpapers — never invent a URL.

6. After writing ``final_report.md`` return its full contents as your final
   answer.

Hard rules:

* Never cite a URL that did not appear in a Perplexity Search result. If the
  sub-agents did not produce a fact, omit it rather than guessing.
* Numbers must be attributed (date, source). If a number is not in the
  workpapers, write "not disclosed".
* Keep the final report under ~700 words.
"""


# ---------------------------------------------------------------------------
# Agent construction
# ---------------------------------------------------------------------------
@dataclass
class AgentConfig:
    """Knobs the CLI and ``investigate_launch`` share."""

    model: str = DEFAULT_MODEL
    api_key: Optional[str] = None
    temperature: float = 0.0


def _build_chat_model(cfg: AgentConfig) -> Any:
    """Return a LangChain chat model backed by Perplexity.

    Uses the official ``langchain-perplexity`` integration when available, and
    falls back to ``ChatOpenAI`` pointed at ``api.perplexity.ai`` otherwise so
    the example still runs in environments that have not pinned the new
    package yet.
    """
    api_key = cfg.api_key or os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set PERPLEXITY_API_KEY (or pass --api-key) before running."
        )

    try:
        from langchain_perplexity import ChatPerplexity

        return ChatPerplexity(
            model=cfg.model,
            temperature=cfg.temperature,
            pplx_api_key=api_key,
        )
    except ImportError:
        pass

    # Fallback: OpenAI-compatible endpoint. Header injection works here.
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=cfg.model,
        temperature=cfg.temperature,
        api_key=api_key,
        base_url="https://api.perplexity.ai",
        default_headers=PPLX_INTEGRATION_HEADER,
    )


def build_agent(cfg: Optional[AgentConfig] = None) -> Any:
    """Construct the deep agent: orchestrator + 4 sub-agents + search tool."""
    cfg = cfg or AgentConfig()

    try:
        from deepagents import create_deep_agent
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "deepagents is required. Install with `pip install deepagents`."
        ) from exc

    chat_model = _build_chat_model(cfg)
    search_tool = make_perplexity_search_tool(cfg.api_key)

    return create_deep_agent(
        model=chat_model,
        tools=[search_tool],
        instructions=ORCHESTRATOR_PROMPT,
        subagents=SUBAGENTS,
    )


# ---------------------------------------------------------------------------
# Programmatic entry point
# ---------------------------------------------------------------------------
def investigate_launch(
    topic: str,
    cfg: Optional[AgentConfig] = None,
    recursion_limit: int = 60,
) -> Dict[str, Any]:
    """Run the agent end-to-end and return the final state.

    The returned dict contains ``messages`` (the full LangGraph trace) and
    ``files`` (the virtual workpapers written by the sub-agents). Callers
    typically want ``files["final_report.md"]``.
    """
    agent = build_agent(cfg)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": topic}]},
        {"recursion_limit": recursion_limit},
    )
    return result


# ---------------------------------------------------------------------------
# Streaming progress (handy for notebooks / long-running runs)
# ---------------------------------------------------------------------------
def stream_launch(
    topic: str,
    cfg: Optional[AgentConfig] = None,
    recursion_limit: int = 60,
) -> Iterable[Tuple[str, Any]]:
    """Yield ``(node_name, state_update)`` tuples as the graph runs.

    Useful for live progress UIs — print one line per yielded tuple.
    """
    agent = build_agent(cfg)
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": topic}]},
        {"recursion_limit": recursion_limit},
        stream_mode="updates",
    ):
        for node, update in chunk.items():
            yield node, update


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_final_report(result: Dict[str, Any]) -> None:
    files = result.get("files", {}) or {}
    if "final_report.md" in files:
        print(files["final_report.md"])
        return
    # No workpaper written — fall back to the last assistant message.
    messages = result.get("messages", []) or []
    if messages:
        last = messages[-1]
        text = getattr(last, "content", None) or (
            last.get("content") if isinstance(last, dict) else ""
        )
        if text:
            print(text)
            return
    print("(no final_report.md produced)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a launch-intelligence brief with a Perplexity-powered "
            "LangChain Deep Agent."
        )
    )
    parser.add_argument(
        "topic",
        help="Launch to investigate, e.g. 'NVIDIA Rubin GPU announcement'.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("PPLX_MODEL", DEFAULT_MODEL),
        help=f"Perplexity chat model (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Perplexity API key (defaults to PERPLEXITY_API_KEY env var).",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream sub-agent progress to stderr while the graph runs.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full final state as JSON instead of the report.",
    )
    parser.add_argument(
        "--recursion-limit",
        type=int,
        default=60,
        help="LangGraph recursion limit (default: 60).",
    )
    args = parser.parse_args(argv)

    cfg = AgentConfig(model=args.model, api_key=args.api_key)
    started = time.time()

    if args.stream:
        # Stream mode: print a one-line progress marker per node update,
        # then print the final report from the last accumulated state.
        last_state: Dict[str, Any] = {}
        try:
            for node, update in stream_launch(args.topic, cfg, args.recursion_limit):
                print(f"[{time.time() - started:6.1f}s] {node}", file=sys.stderr)
                if isinstance(update, dict):
                    last_state.update(update)
        except Exception as err:  # noqa: BLE001
            print(f"Agent error: {err}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(last_state, indent=2, default=str))
        else:
            _print_final_report(last_state)
        return 0

    try:
        result = investigate_launch(args.topic, cfg, args.recursion_limit)
    except Exception as err:  # noqa: BLE001
        print(f"Agent error: {err}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        _print_final_report(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
