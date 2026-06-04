from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_exa import ExaSearchResults
from langchain_parallel import ParallelSearchTool
from langchain_perplexity import ChatPerplexity, PerplexitySearchResults
from langgraph.graph import END, START, StateGraph

from . import _compat  # noqa: F401  temporary tool-loop shim; see _compat docstring
from .graph import (
    GUIDANCE, RESEARCH_PROMPT, MemoState, SYNTH_PROMPT,
)


# Rich tool descriptions teach the LLM to use date filters and multi-query
# variants when calling each provider — small change, big impact on coverage.
TOOL_DESCRIPTIONS = {
    "perplexity_search_results_json": (
        "Perplexity Search API: ranked web results with title, URL, snippet, and date. "
        "Pass `query` as a list of 2-3 diverse phrasings and set "
        "`search_recency_filter=\"year\"` for time-sensitive lookups."
    ),
    "parallel_web_search": (
        "Parallel Search API: pass `objective` as a one-sentence research goal plus "
        "`search_queries` as 2-3 short keyword variants (3-6 words each)."
    ),
    "exa_search_results_json": (
        "Exa Search API: pass `query` as a natural-language string and set "
        "`start_published_date` to ~12 months ago for time-sensitive lookups."
    ),
}


@dataclass
class ProviderProfile:
    name: str
    build_graph: Callable[[], Any]


def _to_flat_function_tool(tool):
    """Convert a LangChain tool to a flat OpenAI function-tool spec for the Responses API."""
    nested = convert_to_openai_tool(tool)
    fn = nested["function"]
    desc = TOOL_DESCRIPTIONS.get(fn["name"], fn.get("description", ""))
    return {"type": "function", "name": fn["name"], "description": desc,
            "parameters": fn.get("parameters", {})}


def _research_node(section, sub_model, search_tool):
    """Build a research node closure that loops tool calls until the model returns a final answer."""
    bound = sub_model.bind(tools=[_to_flat_function_tool(search_tool)])

    def _research(state: MemoState) -> dict:
        """Run the tool-calling loop for this section and return its research output."""
        history = [
            {"role": "system", "content": RESEARCH_PROMPT.format(
                section=section, company=state["company"], guidance=GUIDANCE[section],
            )},
            {"role": "user", "content": f"Research the {section} of {state['company']}."},
        ]
        for _ in range(8):
            msg = bound.invoke(history)
            if not getattr(msg, "tool_calls", None):
                return {"research_output": {section: msg.content}}
            history.append(msg)
            for tc in msg.tool_calls:
                result = search_tool.invoke(tc["args"])
                history.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})
        return {"research_output": {section: msg.content}}

    return _research


def _build_graph_for(sub_model, synth_model, search_tool):
    """Build a StateGraph wired with the given models and a single search tool for all research nodes."""
    def _synth(state: MemoState) -> dict:
        """Synthesize the final memo from all research outputs."""
        research_output_block = "\n\n".join(
            f"## Research output: {name}\n\n{body}"
            for name, body in sorted(state["research_output"].items())
        )
        msg = synth_model.invoke([
            {"role": "system", "content": SYNTH_PROMPT.format(company=state["company"])},
            {"role": "user", "content": f"Company: {state['company']}\n\nResearch outputs:\n\n{research_output_block}"},
        ])
        return {"memo": msg.content}

    g = StateGraph(MemoState)
    g.add_node("synthesizer", _synth)
    for section in ("team", "financials", "product", "market"):
        g.add_node(section, _research_node(section, sub_model, search_tool))
        g.add_edge(START, section)
        g.add_edge(section, "synthesizer")
    g.add_edge("synthesizer", END)
    return g.compile()


def _model() -> ChatPerplexity:
    """Build the shared ChatPerplexity client used by every provider profile."""
    return ChatPerplexity(model="openai/gpt-5.5", use_responses_api=True)


def _build(search_tool):
    """Shortcut: build a graph using the default model for both subnodes and synthesizer."""
    return _build_graph_for(sub_model=_model(), synth_model=_model(), search_tool=search_tool)


PROFILES = {
    "perplexity": ProviderProfile("perplexity", lambda: _build(PerplexitySearchResults(max_results=8))),
    "parallel":   ProviderProfile("parallel",   lambda: _build(ParallelSearchTool(max_results=8))),
    "exa":        ProviderProfile("exa",        lambda: _build(ExaSearchResults(num_results=8))),
}
