.PHONY: sync up down setup doctor customers enrich results test reset smoke-readme

sync:
	uv sync --frozen

up:
	docker compose up -d

down:
	docker compose down

setup:
	uv run customer-enrichment setup

doctor:
	uv run customer-enrichment doctor

customers:
	uv run customer-enrichment customers

enrich:
	uv run customer-enrichment enrich --limit 3

results:
	uv run customer-enrichment results

test:
	uv run pytest

reset:
	uv run customer-enrichment reset

smoke-readme:
	uv run python scripts/smoke_readme.py --mode local
