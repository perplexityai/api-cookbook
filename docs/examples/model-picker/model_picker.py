#!/usr/bin/env python3
"""Model Picker - turn a plain-language task into a grounded shortlist of open
models, using one Agent API request that combines the Hugging Face MCP server
with web search. See the README for details.
"""

import argparse
import os
import sys
import time
from typing import Any, List

from perplexity import Perplexity

POLL_INTERVAL_SECONDS = 4
POLL_TIMEOUT_SECONDS = 600
MAX_STEPS = 20
MODEL = "openai/gpt-5.5"
HF_MCP_URL = "https://huggingface.co/mcp"

# Read-only subset of the server's tools, so the model can look up models but nothing else.
HF_ALLOWED_TOOLS = [
    "hub_repo_search",
    "hub_repo_details",
    "paper_search",
    "hf_doc_search",
    "hf_doc_fetch",
]

# Force the model to verify against the tools instead of answering from memory.
INSTRUCTIONS = """You recommend open models from Hugging Face for a user's task.

Ground every claim in tools - never recommend a model from memory:
- Find candidates with hub_repo_search. If a search returns weak or empty
  results, refine it (change the query wording, task filter, or sort) and
  search again before giving up.
- For each finalist, call hub_repo_details to confirm its real task, license,
  download count, and last-modified date. Drop candidates you cannot verify.
- Use web_search to check each finalist's benchmarks, quality, and any known
  issues or deprecations. Always run at least one web_search before you
  recommend.

Then answer in Markdown:
1. A shortlist table with columns: Model | Downloads | License | Hugging Face link.
2. One recommendation with a short justification tied to the task's
   constraints, citing the Hub links and the web sources you used.
Prefer models with a clear open license and real adoption over obscure repos."""

PROMPT_TEMPLATE = """Recommend an open model for this task:

{task}

Search Hugging Face for candidates, verify each with its repo details, and
check the web for benchmarks and known issues before recommending one."""


def build_tools() -> List[dict]:
    mcp_tool = {
        "type": "mcp",
        "server_label": "huggingface",
        "server_url": HF_MCP_URL,
        "allowed_tools": HF_ALLOWED_TOOLS,
    }
    # Optional: set HF_TOKEN to authenticate and raise the anonymous rate limit.
    token = os.environ.get("HF_TOKEN")
    if token:
        mcp_tool["authorization"] = token
    return [mcp_tool, {"type": "web_search"}]


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


def final_text(response: Any) -> str:
    # Built by hand: response.output_text raises when a message block has no text.
    chunks: List[str] = []
    for item in response.output or []:
        if getattr(item, "type", None) != "message":
            continue
        for block in getattr(item, "content", None) or []:
            if getattr(block, "type", None) == "output_text" and block.text:
                chunks.append(block.text)
    return "\n\n".join(chunks)


def print_tool_trace(response: Any) -> None:
    # MCP calls arrive as mcp_call items; web searches as search_results items.
    print("--- tool trace ---", file=sys.stderr)
    n = 0
    for item in response.output or []:
        kind = getattr(item, "type", None)
        if kind == "mcp_call":
            n += 1
            print(f"\n{n}. mcp:{item.name} {(item.arguments or '').strip()[:200]}", file=sys.stderr)
        elif kind == "search_results":
            n += 1
            queries = getattr(item, "queries", None) or []
            print(f"\n{n}. web_search {'; '.join(queries)}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recommend an open model for a task.")
    parser.add_argument(
        "task",
        help='The task in plain language, e.g. "on-device English speech-to-text".',
    )
    parser.add_argument(
        "--show-tools",
        action="store_true",
        help="Print the tool calls the model made, in order.",
    )
    args = parser.parse_args()

    if not os.environ.get("PERPLEXITY_API_KEY"):
        print("Set PERPLEXITY_API_KEY in your environment.", file=sys.stderr)
        return 1

    client = Perplexity()
    print(f"Finding open models for: {args.task}", file=sys.stderr)
    try:
        response = submit_and_wait(
            client,
            model=MODEL,
            instructions=INSTRUCTIONS,
            input=PROMPT_TEMPLATE.format(task=args.task),
            tools=build_tools(),
            max_steps=MAX_STEPS,
        )
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

    if args.show_tools:
        print_tool_trace(response)
    print(final_text(response) or "(no answer returned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
