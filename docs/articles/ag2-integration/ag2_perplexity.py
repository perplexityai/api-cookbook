"""Perplexity + AG2: a research agent with web search and grounded answers.

Requires AG2 >= 1.0.0:

    pip install "ag2[perplexity,anthropic]>=1.0.0"

    export PERPLEXITY_API_KEY="..."
    export ANTHROPIC_API_KEY="..."

Run:

    python ag2_perplexity.py
"""

import asyncio

from ag2 import Agent
from ag2.config import AnthropicConfig
from ag2.tools import PerplexitySearchToolkit

# api_key is omitted, so the Perplexity SDK reads PERPLEXITY_API_KEY from the environment.
toolkit = PerplexitySearchToolkit()

# Raw Search API results — ranked sources, no LLM hop.
search_tool = toolkit.search(
    max_results=10,
    search_recency_filter="month",
)

# Sonar answer with citations.
answer_tool = toolkit.answer(
    model="sonar-pro",
    search_context_size="high",
    return_related_questions=True,
)

agent = Agent(
    "researcher",
    prompt=(
        "You research topics on the live web.\n"
        "Use perplexity_search to gather candidate sources, then perplexity_answer "
        "for a grounded summary. Always cite the URLs you relied on."
    ),
    config=AnthropicConfig(model="claude-sonnet-4-6"),
    tools=[search_tool, answer_tool],
)


async def main() -> None:
    reply = await agent.ask("What shipped in the latest Sonar model release?")
    print(reply.body)


if __name__ == "__main__":
    asyncio.run(main())
