#!/usr/bin/env python3
"""Build a vetted sourcing shortlist of engineers. The model runs code in a
sandbox: it finds candidates by segment with people_search, verifies each with
web_search - confirming role, location, and tenure, and collecting GitHub,
social, and publication links - then writes an HTML table and shares it. We
download the file."""

import argparse
import os
import re
import sys
from datetime import datetime

from perplexity import Perplexity

MODEL = "openai/gpt-5.5"
PROGRESS_PREFIX = "PROGRESS:"

DEFAULT_ROLE = "engineers"
DEFAULT_SKILL = "LLM inference"
DEFAULT_LOCATION = "NYC"
DEFAULT_MIN_TENURE = 3
DEFAULT_TARGET = 25

COLUMNS = ["Name", "Title", "Company", "Location", "Tenure", "Relevance", "Links", "Verified"]

SOURCER_SYSTEM = (
    "You assemble a vetted sourcing shortlist of technical candidates for a "
    "recruiter. This is a WIDE collection task: completeness, hard-filter "
    "matching, and per-row verification matter more than depth on any one person."
)
SOURCER_TASK = """\
Build a vetted sourcing shortlist of {brief}.
Return exactly {target} candidates: the top {target} by relevance score.

Hard filters every kept candidate must satisfy:
{filters}

Workflow, organized in the Python sandbox:

1. Find candidates with people_search. Run several targeted searches across
   sub-segments (sub-skills, seniority levels, nearby employers, the location)
   rather than one broad query, so coverage is exhaustive.

2. Verify EACH candidate with web_search against the hard filters: confirm their
   current title and company, that they are based in the target location, and how
   long they have been at their current company. Then collect their public links:
   a GitHub profile, another relevant public profile, and a notable
   publication, talk, or open-source project - each a real source URL. If you
   cannot confirm a filter or a link, keep the person but set verified=false.
   Never invent a role, company, tenure, or URL.

3. In code: collect rows, deduplicate by (name, company), drop candidates that
   clearly fail a hard filter, assign a relevance_score from 0-100 against the
   brief, sort by score descending, and keep the top {target}.

4. Render an HTML file named 'candidates.html': a clean, styled page with a
   heading (the brief and the final count) and a table with these columns:
   {columns}. In 'Links', render each collected URL as a labeled link
   (GitHub, Profile, Publication). Show 'Tenure' in years at the current company
   and 'Verified' as yes/no. Share it with share_file.

As you work, print() a short, human-readable status line from your sandbox code at
the start of each phase, prefixed with 'PROGRESS:' - for example
'PROGRESS: Searching for candidates', 'PROGRESS: Verifying candidate 5/40',
'PROGRESS: Rendering shortlist'. Never put tool names, query strings, or raw
result counts in these lines, and do not narrate progress in your reply.

Keep your final reply to one short sentence, then a single line:
TOTAL=<number of candidates in the table>.
"""


def build_brief(role, skill, location):
    brief = f"{role} with hands-on experience in {skill}"
    return f"{brief} based in {location}" if location else brief


def build_filters(skill, location, min_tenure):
    lines = [f"- Hands-on experience in {skill}."]
    if location:
        lines.append(f"- Currently based in {location}.")
    if min_tenure > 0:
        lines.append(f"- At least {min_tenure} years at their current company.")
    return "\n".join(lines)


def progress_lines(event):
    for result in event.model_dump().get("results") or []:
        for line in (result.get("stdout") or "").splitlines():
            if line.startswith(PROGRESS_PREFIX):
                yield line[len(PROGRESS_PREFIX):].strip()


def stream_run(client, **create_kwargs):
    final, last = None, None
    for event in client.responses.create(stream=True, **create_kwargs):
        if event.type == "response.output_text.delta":
            print(event.delta, end="", flush=True)
        elif event.type == "response.sandbox.results":
            for line in progress_lines(event):
                if line != last:
                    print(f"  · {line}", file=sys.stderr)
                    last = line
        elif event.type == "response.completed":
            final = event.response
    print()
    return final


def find_candidates(client, brief, filters, target):
    return stream_run(
        client,
        model=MODEL,
        instructions=SOURCER_SYSTEM,
        input=SOURCER_TASK.format(
            brief=brief, filters=filters, target=target, columns=", ".join(COLUMNS)
        ),
        tools=[{"type": "sandbox"}],
    )


def final_text(response):
    return "".join(
        block.text
        for item in response.output if item.type == "message"
        for block in item.content if block.type == "output_text"
    )


def cost(response):
    usage = getattr(getattr(response, "usage", None), "cost", None)
    return float(getattr(usage, "total_cost", 0.0) or 0.0)


def download_html(client, response, output):
    files = client.responses.files.list(response.id)
    html = next(f for f in files.data if f.filename.lower().endswith(".html"))
    out_path = output or f"candidate-shortlist-{datetime.now():%Y-%m-%d_%H-%M}.html"
    client.responses.files.content(html.id, response_id=response.id).write_to_file(out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Build a vetted engineer sourcing shortlist.")
    parser.add_argument("--role", default=DEFAULT_ROLE)
    parser.add_argument("--skill", default=DEFAULT_SKILL)
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--min-tenure", type=int, default=DEFAULT_MIN_TENURE)
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET)
    parser.add_argument("--output")
    args = parser.parse_args()

    if not os.environ.get("PERPLEXITY_API_KEY"):
        sys.exit("Set PERPLEXITY_API_KEY in your environment.")

    client = Perplexity()
    brief = build_brief(args.role, args.skill, args.location)
    filters = build_filters(args.skill, args.location, args.min_tenure)

    print(f"\nSourcing a vetted shortlist of: {brief} (target {args.target})\n", file=sys.stderr)
    response = find_candidates(client, brief, filters, args.target)
    out_path = download_html(client, response, args.output)

    match = re.search(r"TOTAL=(\d+)", final_text(response))
    total = match.group(1) if match else "?"
    print(f"\nCandidates: {total}   ${cost(response):.4f}", file=sys.stderr)
    print(f"Saved shortlist to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
