"""Optional observability helpers for the Competitor Buzz Tracker.

Kept in a separate module so the main script stays focused on the Agent API
calls. Nothing here is on the critical path (cost reporting and showing the
code the model ran), so it could later move into shared tooling or the SDK.
"""

import sys
from typing import Any, List, Tuple


def print_costs(stages: List[Tuple[str, Any]]) -> None:
    """Print per-request cost and the combined total to stderr."""
    amounts: List[float] = []
    currency = "USD"
    for label, response in stages:
        cost = getattr(getattr(response, "usage", None), "cost", None)
        total = getattr(cost, "total_cost", None)
        if total is not None:
            currency = getattr(cost, "currency", "USD")
            amounts.append(total)
            print(f"{label} cost: {total:.4f} {currency}", file=sys.stderr)
    if amounts:
        print(f"Total cost: {sum(amounts):.4f} {currency}", file=sys.stderr)


def sandbox_code(response: Any) -> List[str]:
    """Return the code cells the model wrote and ran in the sandbox."""
    cells: List[str] = []
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) != "sandbox_results":
            continue
        data = item.model_dump() if hasattr(item, "model_dump") else {}
        code = data.get("code")
        if code:
            cells.append(code)
    return cells


def print_sandbox_code(response: Any, label: str = "") -> None:
    """Print the code the model ran in the sandbox (for inspection)."""
    cells = sandbox_code(response)
    if not cells:
        return
    where = f" [{label}]" if label else ""
    print(f"--- sandbox code{where} ---", file=sys.stderr)
    for i, code in enumerate(cells, 1):
        print(f"\n# cell {i}/{len(cells)}", file=sys.stderr)
        print(code, file=sys.stderr)
