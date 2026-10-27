import asyncio
from langsmith import Client
from langsmith.evaluation import evaluate

from .eval_dataset import EVAL_COMPANIES
from .evaluators import primary_source_rate, financial_concept_coverage
from .profiles import PROFILES, ProviderProfile

DATASET_NAME = "vc-memo-eval-v2"
client = Client()


def upload_dataset() -> None:
    """Create the LangSmith eval dataset from EVAL_COMPANIES if it doesn't already exist."""
    if any(d.name == DATASET_NAME for d in client.list_datasets()):
        return
    dataset = client.create_dataset(DATASET_NAME, description="VC memo evaluation")
    for company in EVAL_COMPANIES:
        client.create_example(
            inputs={"company": company},
            outputs={},
            dataset_id=dataset.id,
        )


async def _run_one(company: str, profile: ProviderProfile) -> dict:
    """Run the memo graph for one company under the given provider profile."""
    graph = profile.build_graph()
    final = await graph.ainvoke({"company": company, "research_output": {}, "memo": ""})
    return {"memo_md": final["memo"]}


def main() -> None:
    """Upload the dataset and run a LangSmith evaluation for each provider profile."""
    upload_dataset()
    for name in ("perplexity", "parallel", "exa"):
        profile = PROFILES[name]
        evaluate(
            lambda inputs, profile=profile: asyncio.run(_run_one(inputs["company"], profile)),
            data=DATASET_NAME,
            evaluators=[primary_source_rate, financial_concept_coverage],
            experiment_prefix=f"memo-{name}",
            max_concurrency=2,
        )


if __name__ == "__main__":
    main()
