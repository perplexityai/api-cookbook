# Contributing to the Perplexity API Cookbook

Contributions should help developers complete a real task with the Agent API, Search API, or Embeddings API. The cookbook accepts runnable examples, in-depth guides, bug fixes, and documentation improvements.

## Content types

### Examples (`docs/examples/`)

Add a self-contained, ready-to-run project that demonstrates a distinct API capability or implementation pattern.

### Guides (`docs/articles/`)

Add an in-depth tutorial for a multi-step workflow, integration, or advanced implementation pattern.

The community showcase category is no longer accepted. Turn a project idea into a reproducible example or guide that teaches readers how to build the relevant API pattern.

## What we're looking for

- Clear educational value and a real-world use case
- A capability not already covered by an existing recipe
- Tested code with explicit prerequisites and setup instructions
- Secure handling of API keys and other credentials
- Expected output, limitations, and cost or latency considerations where relevant
- Required `title`, `description`, `products`, and optional `categories` frontmatter matching nearby pages

New content must not use Sonar models, Chat Completions endpoints, or Sonar-specific response parsing. Use `client.responses.create()` or the Agent API HTTP endpoint for hosted-agent workflows, `client.search.create()` for raw search results, and the embeddings methods for vector generation.

## Submission format

Create a directory under `docs/examples/your-example-name/` or `docs/articles/your-guide-name/`. Add a `README.mdx` and any runnable source, dependency, and asset files it needs.

Use this page structure:

```mdx
---
title: Your Recipe Title
description: A concise description of the task and API capability
keywords: [relevant, keywords]
products: [agent-api]
categories: [relevant-category]
---

# Your Recipe Title

Briefly explain what the reader will build and why it is useful.

## Prerequisites

List required software, access, and environment variables.

## Installation

Provide complete setup commands.

## Usage

Show runnable commands and representative output.

## How it works

Explain the important API calls and implementation decisions.

## Limitations

Describe operational, quality, safety, and cost tradeoffs.
```

## Pull requests

1. Fork this repository and create a focused branch.
2. Add or update the recipe and its runnable files.
3. Run `npm ci` and `node scripts/validate-mdx.js`.
4. Run the example against the live API and redact credentials from any proof.
5. Open a pull request using the repository template.

Large additions should start with an issue so maintainers can confirm the proposed recipe does not overlap existing content.

## Code quality

- Use clear names and idiomatic language conventions.
- Comment decisions and non-obvious constraints, not straightforward code.
- Handle API and network failures explicitly.
- Read credentials from environment variables; never commit keys.
- Pin or constrain dependencies where reproducibility requires it.

Questions can be raised in a GitHub issue or sent to api@perplexity.ai.
