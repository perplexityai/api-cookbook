# Contributing a showcase project

Submit a community showcase page for a project built with the Perplexity Agent API, Search API, Embeddings API, or Decisions API. Maintainers review submissions for the [cookbook gallery](https://docs.perplexity.ai/docs/cookbook).

Tutorials, guides, and runnable examples are authored in the docs, not here. If you have one of those, open an issue describing it and we will route it.

## Requirements

- Your project uses the Agent API, Search API, Embeddings API, or Decisions API. Sonar-only projects (`/chat/completions`) are not accepted.
- The project has its own public repository or a live URL. The showcase page describes it and links out; it does not host the code.
- One MDX file at `docs/showcase/<your-project-slug>.mdx`. Lowercase, hyphens, no spaces.
- Images are either hosted on https URLs you control or committed under `static/showcase/<your-project-slug>/`.
- No imports, executable expressions, scripts, or embeds other than a YouTube iframe.

## Two ways to submit

**Issue.** Open an issue with the project URL, a description, and how it uses the API. A maintainer can help prepare the showcase page.

**Direct PR.** Fork the repo, add your MDX file using the template below, and open a PR against `main`.

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
| `products` | yes | One or more of `agent-api`, `search-api`, `embeddings-api`, `decisions-api` |
| `categories` | no | Any of `finance`, `people`, `sandbox`, `multimodal`, `rag`, `deep-research`, `structured-outputs`, `function-calling`, `streaming`, `memory`, `search-filtering`, `orchestration`, `integrations`, `mcp` |

`products` and `categories` drive the filters in the docs gallery. Pick the ones a developer would use to find your project.

## What gets a project declined

- Sonar-only, or no Perplexity API call at all.
- No public repo and no live URL.
- Content that is mostly marketing copy with no explanation of how the API is used.
- Anything that fails validation: bad frontmatter, disallowed imports or embeds, images from http URLs.
- Duplicate of an existing showcase project.

## Review and publication

1. The submission must pass CI and maintainer review.
2. After merge, a docs maintainer reviews and publishes the page in the gallery. A merged submission is not yet a published page.

Submit later edits to the page here so maintainers can carry the changes to the gallery.

## Questions

Open an issue, or ask in the [community forum](https://community.perplexity.ai).
