import re
from urllib.parse import urlparse
from langsmith.evaluation import EvaluationResult, run_evaluator

URL_RE = re.compile(r"https?://\S+")

PRIMARY_HOST_RE = re.compile(
    r"(^|\.)(investors?|ir|investorrelations?|press|news|newsroom|press-?releases?|media)\.",
    re.IGNORECASE,
)
PRIMARY_DOMAINS = {"sec.gov", "edgar.sec.gov", "businesswire.com",
                   "prnewswire.com", "globenewswire.com"}
AGGREGATOR_DOMAINS = {"en.wikipedia.org", "crunchbase.com", "pitchbook.com",
                      "simplywall.st", "stockanalysis.com", "finance.yahoo.com",
                      "reddit.com", "medium.com", "macrotrends.net"}


def _classify(url: str, company: str) -> str:
    """Classify a cited URL as primary, aggregator, or neutral source."""
    host = urlparse(url).netloc.lower()
    if host in PRIMARY_DOMAINS or PRIMARY_HOST_RE.search(host):
        return "primary"
    co_words = [w.lower() for w in company.split() if len(w) > 3]
    if any(w in host for w in co_words):
        return "primary"        # Company's own domain counts as primary
    if host in AGGREGATOR_DOMAINS:
        return "aggregator"
    return "neutral"


@run_evaluator
def primary_source_rate(run, example) -> EvaluationResult:
    """Share of citations from primary sources (IR pages, SEC, official press)
    rather than aggregators (Wikipedia, Crunchbase). Neutral domains are
    excluded from the ratio."""
    memo = run.outputs["memo_md"]
    company = example.inputs["company"]
    urls = [u.rstrip(".,)") for u in URL_RE.findall(memo)]
    primary = sum(1 for u in urls if _classify(u, company) == "primary")
    aggregator = sum(1 for u in urls if _classify(u, company) == "aggregator")
    denom = primary + aggregator
    score = primary / denom if denom else None
    return EvaluationResult(key="primary_source_rate", score=score)


@run_evaluator
def financial_concept_coverage(run, example) -> EvaluationResult:
    """Of four financial concepts (valuation, revenue/ARR, funding, operating
    metrics), how many appear in the Financials section?"""
    memo = run.outputs["memo_md"]
    m = re.search(r"##.*Financials.*?\n(.*?)(?=\n##\s|\Z)", memo, re.DOTALL | re.IGNORECASE)
    if not m:
        return EvaluationResult(key="financial_concept_coverage", score=0.0)
    body = m.group(1).lower()
    hits = sum([
        bool(re.search(r"valuation|valued at|market cap|post-money|pre-money", body)),
        bool(re.search(r"revenue|arr |annual recurring|run.?rate", body)),
        bool(re.search(r"raised|series [a-h]|funding round|total funding", body)),
        bool(re.search(r"gross margin|operating margin|cash position|growth|customers|headcount|employees", body)),
    ])
    return EvaluationResult(key="financial_concept_coverage", score=hits / 4)
