# Contributing a showcase project

This repo accepts one kind of contribution: a community showcase page for a project you built with the Perplexity Agent API, Search API, or Embeddings API. Merged pages sync to the [cookbook gallery](https://docs.perplexity.ai/docs/cookbook) on docs.perplexity.ai.

Tutorials, guides, and runnable examples are authored in the docs, not here. If you have one of those, open an issue describing it and we will route it.

## Requirements

- Your project uses the Agent API, Search API, or Embeddings API. Sonar-only projects (`/chat/completions`) are not accepted; Sonar shuts down on 2026-09-27.
- The project has its own public repository or a live URL. The showcase page describes it and links out; it does not host the code.
- One MDX file at `docs/showcase/<your-project-slug>.mdx`. Lowercase, hyphens, no spaces.
- Images are either hosted on https URLs you control or committed under `static/showcase/<your-project-slug>/`.
- No arbitrary imports, scripts, or embeds. The only iframe allowed is a YouTube embed. Validation rejects anything else.

## Two ways to submit

**Issue form (recommended).** Open a [showcase submission](https://github.com/perplexityai/api-cookbook/issues/new?template=showcase.yml) and fill in the fields. A maintainer turns it into a PR for you. You do not need to write MDX.

**Direct PR.** Fork the repo, add your MDX file using the template below, open a PR against `main`. CI validates the frontmatter and content rules. A code owner reviews and merges.

## MDX template

```mdx
---
title: Project Name
description: One sentence. What it does and who it is for.
keywords: [three, to, eight, lowercase, keywords]
products: [agent-api]
categories: [orchestration, integrations]
---

![Screenshot of Project Name](https://your-domain.example/screenshot.png)

**Project Name** does X for Y. Two or three sentences on the problem it solves.

## How it uses the Perplexity API

Which API and which features (web search, finance_search, sandbox, structured outputs, profiles, and so on). Two paragraphs at most. Code snippets are welcome if they show the Perplexity call.

## Try it

- [Repository](https://github.com/you/project)
- [Live demo](https://project.example) (optional)

## Built by

Your name or handle, and how people can reach you (optional).
```

### Frontmatter fields

| Field | Required | Allowed values |
|---|---|---|
| `title` | yes | Free text, under 60 characters |
| `description` | yes | One sentence, under 160 characters |
| `keywords` | yes | 3 to 8 lowercase strings |
| `products` | yes | One or more of `agent-api`, `search-api`, `embeddings-api` |
| `categories` | no | Any of `finance`, `people`, `sandbox`, `multimodal`, `rag`, `deep-research`, `structured-outputs`, `function-calling`, `streaming`, `memory`, `search-filtering`, `orchestration`, `integrations`, `mcp` |

`products` and `categories` drive the filters in the docs gallery. Pick the ones a developer would use to find your project.

## What gets a project declined

- Sonar-only, or no Perplexity API call at all.
- No public repo and no live URL.
- Content that is mostly marketing copy with no explanation of how the API is used.
- Anything that fails validation: bad frontmatter, disallowed imports or embeds, images from http URLs.
- Duplicate of an existing showcase project.

## Review and sync

1. CI runs on your PR: MDX compiles, frontmatter matches the schema, content rules pass.
2. A code owner (see `.github/CODEOWNERS`) reviews. Expect a first response within a week. If it has been longer, comment on the PR.
3. On merge, a workflow copies your page into the docs repository and opens a PR there. A docs maintainer merges it and the page goes live within a day.

Edits after publication go through the same path: change the file here, open a PR. Do not ask for edits to the docs copy directly; the next sync would overwrite them.

## Questions

Open an issue, or ask in the [community forum](https://community.perplexity.ai).
