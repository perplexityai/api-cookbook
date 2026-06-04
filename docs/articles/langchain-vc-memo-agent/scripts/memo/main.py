import argparse
import asyncio

from .graph import build_graph


async def run_memo(company: str) -> str:
    """Run the full memo agent for one company and return the final markdown memo."""
    graph = build_graph()
    final = await graph.ainvoke({"company": company, "research_output": {}, "memo": ""})
    return final["memo"]


def main() -> None:
    """CLI entrypoint: parse `--company` and print the generated memo."""
    parser = argparse.ArgumentParser(description="VC investment memo agent.")
    parser.add_argument("--company", required=True)
    args = parser.parse_args()
    print(asyncio.run(run_memo(args.company)))


if __name__ == "__main__":
    main()
