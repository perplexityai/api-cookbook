# Perplexity API Cookbook

Practical guides and runnable examples for building with Perplexity's [Agent API](https://docs.perplexity.ai/docs/agent-api/quickstart), [Search API](https://docs.perplexity.ai/docs/search/quickstart), and [Embeddings API](https://docs.perplexity.ai/docs/embeddings/quickstart).

The rendered cookbook is available at [docs.perplexity.ai/docs/cookbook](https://docs.perplexity.ai/docs/cookbook/).

## What's inside

- [`docs/examples/`](docs/examples/) contains ready-to-run applications, including research agents, document Q&A, finance workflows, sandbox artifacts, and Search API monitors.
- [`docs/articles/`](docs/articles/) contains deeper guides for Agent API tools, structured outputs, RAG, streaming citations, and framework integrations.
- [`SONAR_AGENT_MIGRATION_BACKLOG.md`](SONAR_AGENT_MIGRATION_BACKLOG.md) preserves the worthwhile ideas removed with the retired Sonar cookbook content.

## Quick start

1. Choose a guide or example under [`docs/`](docs/).
2. Follow its prerequisites and installation instructions.
3. Create an API key in the [API Portal](https://perplexity.ai/account/api).
4. Export the key before running an example:

```bash
export PERPLEXITY_API_KEY="your-api-key-here"
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) to propose a guide, runnable example, fix, or documentation improvement. New recipes should teach a distinct Agent, Search, or Embeddings API capability and include tested code.

## Publishing

The `sync-to-docs.yml` workflow mirrors `docs/` and `static/` into [`ppl-ai/api-docs/docs/cookbook`](https://github.com/ppl-ai/api-docs/tree/main/docs/cookbook), then regenerates the Mintlify navigation and gallery data. This repository is the source of truth for cookbook content.
