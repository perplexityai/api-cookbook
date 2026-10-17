# Perplexity API Cookbook: Community Showcase

Built something with the [Perplexity Agent API](https://docs.perplexity.ai/docs/agent-api/quickstart), [Search API](https://docs.perplexity.ai/docs/search/quickstart), Embeddings API, or Decisions API? This is where you submit it. Accepted projects appear in the [cookbook gallery on docs.perplexity.ai](https://docs.perplexity.ai/docs/cookbook) under Showcase.

## What this repo is for

One thing: community showcase projects. You open a PR (or fill in the issue form), a maintainer reviews it, and once it merges the page syncs to the docs site.

Tutorials, guides, and runnable examples are written and maintained directly in the docs. They do not live here anymore. If you want to propose one, open an issue and we will point you to the right place.

## Submit your project

1. Build your project in its own public repository.
2. Either
   - open a [showcase submission issue](https://github.com/perplexityai/api-cookbook/issues/new?template=showcase.yml) and fill in the form, or
   - fork this repo, add `docs/showcase/your-project.mdx` using the template in [CONTRIBUTING.md](CONTRIBUTING.md), and open a PR.
3. A maintainer reviews it. Once merged, the page appears on docs.perplexity.ai within a day.

Projects must use the Agent API, Search API, Embeddings API, or Decisions API. The Sonar API (`/chat/completions`) is deprecated and Sonar-only projects are not accepted. If you are still on Sonar, start with the [migration guide](https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar/overview).

## What happened to the examples in this repo?

`docs/examples/` and `docs/articles/` are frozen for new contributions. They contain both legacy Sonar material and examples that already use the Agent API. Check each example's API and dependencies before running it. Current maintained examples live in the [cookbook](https://docs.perplexity.ai/docs/cookbook).

Legacy showcase pages are being retired from this repository. Browse the current [cookbook gallery](https://docs.perplexity.ai/docs/cookbook) for maintained entries.

## Resources

- [Agent API documentation](https://docs.perplexity.ai/docs/agent-api/quickstart)
- [Search API documentation](https://docs.perplexity.ai/docs/search/quickstart)
- [Cookbook](https://docs.perplexity.ai/docs/cookbook)
- [Migrate from Sonar](https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar/overview)
- [Community forum](https://community.perplexity.ai)
