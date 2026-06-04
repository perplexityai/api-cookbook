from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage
from langchain_perplexity import ChatPerplexity
from langgraph.graph import END, START, StateGraph


def merge_research_output(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    """Each research node returns {"<section>": "..."}; merge into one dict."""
    return {**(left or {}), **(right or {})}


class MemoState(TypedDict):
    company: str
    research_output: Annotated[dict[str, str], merge_research_output]
    memo: str


SUBNODE_MODEL_NAME = "openai/gpt-5.5"
SYNTHESIZER_MODEL_NAME = "openai/gpt-5.5"


def _agent_model(model: str) -> ChatPerplexity:
    """Build a ChatPerplexity client wired to the Responses API."""
    # The Responses (Agent) API ignores sampling params like temperature, so we omit it.
    return ChatPerplexity(model=model, use_responses_api=True)


SUBNODE_MODEL = _agent_model(SUBNODE_MODEL_NAME)
SYNTHESIZER_MODEL = _agent_model(SYNTHESIZER_MODEL_NAME)


# Per-research-node tool specs.
TEAM_TOOLS = [{
    "type": "web_search",
    "filters": {"search_recency_filter": "year"},
}]

PRODUCT_TOOLS = [{"type": "web_search"}]

MARKET_TOOLS = [{"type": "web_search"}]

FINANCIALS_TOOLS = [{"type": "finance_search"}, {"type": "web_search"}]


# Per-research-node max_steps caps the Perplexity Agent API's internal search loop.
RESEARCH_MAX_STEPS = {
    "team": 2, "financials": 5, "product": 2, "market": 2,
}


RESEARCH_PROMPT = """You are a VC analyst writing the {section} section of the research output for {company}.

{guidance}

Return a markdown section, then end the document with a "### Citations" header \
followed by a markdown list of:

  - <url> — one-sentence evidence quoted from the source

Cite only URLs that came back from your tool calls; never fabricate URLs. \
Keep the section focused — 250-400 words is appropriate for the body."""


GUIDANCE = {
    "team": (
        "Search for the founders, CEO, and other named executives. Capture each "
        "leader's prior roles and education. Prioritize the company's own About/Team "
        "page and professional-network sources."
    ),
    "financials": (
        "If the company is public, use finance_search for revenue, margins, and analyst "
        "estimates. If private, use web_search for funding rounds, valuation, and "
        "disclosed revenue. Cross-check structured data against recent news."
    ),
    "product": (
        "Describe the company's flagship product, recent launches, and technical "
        "differentiators. Cite the company's own product or engineering pages where "
        "possible, plus tech-press coverage for context."
    ),
    "market": (
        "Map the competitive landscape, name direct competitors, and surface market "
        "sizing. Your web_search is scoped to analyst and trade-press sources."
    ),
}


def _run_research(
    state: MemoState,
    *,
    section: str,
    tools: list[dict[str, Any]],
    max_steps: int,
) -> dict[str, dict[str, str]]:
    """Run one research section with the given tools and return its output."""
    msg: AIMessage = SUBNODE_MODEL.invoke(
        [
            {"role": "system", "content": RESEARCH_PROMPT.format(
                section=section, company=state["company"], guidance=GUIDANCE[section],
            )},
            {"role": "user", "content": f"Research the {section} of {state['company']}."},
        ],
        tools=tools,
        extra_body={"max_steps": max_steps},
    )
    return {"research_output": {section: msg.content}}


def team_node(state):
    """Research the founders and leadership team."""
    return _run_research(state, section="team",
        tools=TEAM_TOOLS, max_steps=RESEARCH_MAX_STEPS["team"])

def financials_node(state):
    """Research revenue, funding, and financial metrics."""
    return _run_research(state, section="financials",
        tools=FINANCIALS_TOOLS, max_steps=RESEARCH_MAX_STEPS["financials"])

def product_node(state):
    """Research the product, launches, and technical differentiators."""
    return _run_research(state, section="product",
        tools=PRODUCT_TOOLS, max_steps=RESEARCH_MAX_STEPS["product"])

def market_node(state):
    """Research the competitive landscape and market sizing."""
    return _run_research(state, section="market",
        tools=MARKET_TOOLS, max_steps=RESEARCH_MAX_STEPS["market"])


SYNTH_PROMPT = """You are a senior VC partner writing the final memo for {company}.

You may only cite evidence that appears in the research outputs below. You have no \
tools; do not browse or fabricate sources.

Produce a markdown memo with these seven sections, in order:

  1. Snapshot — what the company is, founded, valuation, positioning (3-4 sentences)
  2. Team — founders, leadership, recent senior hires
  3. Financials — revenue, growth, funding history, comparables
  4. Product — what they sell, technology, distribution
  5. Market — TAM, direct competitors, category dynamics
  6. Risks — top 3-5 risks with brief reasoning
  7. Thesis — 1-2 paragraphs of analysis, ending with a single line:
     "Recommendation: <PASS | TRACK | ADVANCE | LEAD>"

Each section's H2 heading must be exactly `## <N> · <Section Name>` \
(e.g. `## 1 · Snapshot`), using a middle-dot separator — the evaluator depends \
on this format.

Each of sections 1-6 must end with a `### Citations` subsection listing the \
<url> — <evidence> pairs drawn from the research outputs. Section 7 (Thesis) does \
not need its own citations.

If a research output lacks evidence for a section, write "Insufficient evidence in \
research outputs." in that section's body instead of guessing."""


def synthesizer_node(state: MemoState) -> dict[str, str]:
    """Combine all research outputs into the final memo. No tools attached."""
    research_output_block = "\n\n".join(
        f"## Research output: {name}\n\n{body}"
        for name, body in sorted(state["research_output"].items())
    )
    msg: AIMessage = SYNTHESIZER_MODEL.invoke([
        {"role": "system", "content": SYNTH_PROMPT.format(company=state["company"])},
        {"role": "user", "content": (
            f"Company: {state['company']}\n"
            f"As-of: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
            f"Research outputs:\n\n{research_output_block}"
        )},
    ])
    return {"memo": msg.content}


def build_graph():
    """Wire the four research nodes in parallel from START into the synthesizer, then END."""
    g = StateGraph(MemoState)
    g.add_node("team", team_node)
    g.add_node("financials", financials_node)
    g.add_node("product", product_node)
    g.add_node("market", market_node)
    g.add_node("synthesizer", synthesizer_node)

    for section in ("team", "financials", "product", "market"):
        g.add_edge(START, section)
        g.add_edge(section, "synthesizer")

    g.add_edge("synthesizer", END)
    return g.compile()
