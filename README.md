# Perplexity API Cookbook: Community Showcase

Built something with the [Perplexity Agent API](https://docs.perplexity.ai/docs/agent-api/quickstart), [Search API](https://docs.perplexity.ai/docs/search/quickstart), or Embeddings API? This is where you submit it. Accepted projects appear in the [cookbook gallery on docs.perplexity.ai](https://docs.perplexity.ai/docs/cookbook) under Showcase.

## What this repo is for

One thing: community showcase projects. You open a PR (or fill in the issue form), a maintainer reviews it, and once it merges the page syncs to the docs site.

Tutorials, guides, and runnable examples are written and maintained directly in the docs. They do not live here anymore. If you want to propose one, open an issue and we will point you to the right place.

## Submit your project

1. Build your project in its own public repository.
2. Either
   - open a [showcase submission issue](https://github.com/perplexityai/api-cookbook/issues/new?template=showcase.yml) and fill in the form, or
   - fork this repo, add `docs/showcase/your-project.mdx` using the template in [CONTRIBUTING.md](CONTRIBUTING.md), and open a PR.
3. A maintainer reviews it. Once merged, the page appears on docs.perplexity.ai within a day.

Projects must use the Agent API, Search API, or Embeddings API. The Sonar API (`/chat/completions`) is deprecated and Sonar-only projects are not accepted. If you are still on Sonar, start with the [migration guide](https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar/overview).

## What happened to the examples in this repo?

`docs/examples/` and `docs/articles/` are frozen. They were written for the Sonar API, which shuts down on 2026-09-27, and the code in them will stop working on that date. Current, tested examples for the Agent API live in the [cookbook](https://docs.perplexity.ai/docs/cookbook). We will decide what to do with the frozen directories by 2026-10-15.

The 26 Sonar-era showcase projects were removed on 2026-09-21. Their URLs on docs.perplexity.ai redirect to the cookbook home.

## Resources

- [Agent API documentation](https://docs.perplexity.ai/docs/agent-api/quickstart)
- [Search API documentation](https://docs.perplexity.ai/docs/search/quickstart)
- [Cookbook](https://docs.perplexity.ai/docs/cookbook)
- [Migrate from Sonar](https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar/overview)
- [Community forum](https://community.perplexity.ai)
