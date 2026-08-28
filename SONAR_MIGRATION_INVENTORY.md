# Sonar cookbook migration inventory

This inventory preserves the cookbook material removed ahead of the September 27, 2026 end of public Sonar Chat Completions support. The deleted files remain available in [`api-cookbook` at `543c229`](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs).

The Agent API migration should use the current migration guide and presets rather than mechanically changing the endpoint. A prior docs commit, [`514a467a`](https://github.com/ppl-ai/api-docs/commit/514a467adff2b418d254ce3ecb22948b00baaab9), contains live-tested Agent API ports for all ten removed first-party examples and guides. It is the best recovery point, but each port must be reviewed against the current Agent API contract before republishing. The later revert, [`b264aca7`](https://github.com/ppl-ai/api-docs/commit/b264aca7), preserves the complete history.

## Recommended Agent API rebuilds

### First-party examples and guides

| Priority | Material | Why it is worth rebuilding | Suggested Agent API shape |
| --- | --- | --- | --- |
| High | [OpenAI Agents integration](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/openai-agents-integration) | Covers a major external agent framework and a nontrivial compatibility boundary. | Revalidate the earlier Responses-based port against the current OpenAI Agents SDK and Agent API compatibility layer. |
| High | [Discord bot](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/discord-py-bot) | Demonstrates a common event-driven integration with streaming and conversation state. | Use `responses.create`, typed stream events, and `previous_response_id` per channel or thread. |
| High | [Fact Checker CLI](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/fact-checker-cli) | Teaches grounded claim verification, evidence extraction, and structured output. | Use a research preset, `web_search`, structured output, and explicit source handling. |
| High | [Memory management](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/memory-management) | Conversation continuity and durable external memory remain broadly useful integration patterns. | Consolidate the summary-buffer and LanceDB variants around Agent API conversation state and current LlamaIndex APIs. |
| Medium | [Daily Knowledge Bot](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/daily-knowledge-bot) | Provides a compact scheduled-automation example that is easy for new developers to adapt. | Use the `fast` or `low` preset with grounded output and retain the scheduling/storage shell. |
| Medium | [Financial News Tracker](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/financial-news-tracker) | Shows recurring monitoring and structured market summaries. | Rebuild only if it adds a scheduled workflow beyond the existing Equity Research Brief and Search News Monitor examples. |

The [Academic Research Finder](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/research-finder) is superseded by the current Academic and Scholarly Search guide. The [Disease Information App](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/disease-qa) should not be restored without a new medical-safety and product review.

### Community concepts

The community pages were submissions rather than maintained reference implementations. Rebuild these concepts as first-party, tested Agent API recipes instead of republishing the old pages unchanged.

| Priority | Source concept | Reusable pattern |
| --- | --- | --- |
| High | [PosterLens](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/posterlens.mdx) | Image/OCR input followed by scholarly web research and cited synthesis. |
| High | [Sonar Chromium Browser](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/sonar-chromium-browser.mdx) | Browser omnibox search and context-menu summarization with streaming responses. |
| High | [PerplexiCart](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexicart.mdx) | Multi-source product research with user constraints, structured recommendations, and citations. |
| High | [PerplexiGrid](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexigrid.mdx) | Natural-language analytics that turns researched data into a structured dashboard. |
| High | [4Point Hoops](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/4point-Hoops.mdx) | Custom sports-data retrieval combined with grounded explanation and comparison. |
| Medium | [CityPulse](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/citypulse-ai-search.mdx) | Location-aware discovery using custom functions plus web search. |
| Medium | [Daily News Briefing](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/daily-news-briefing.mdx) | Scheduled research delivered into an Obsidian workflow. |
| Medium | [StarPlex](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/starplex.mdx) | Multi-step market and competitor research for startup validation. |
| Consolidate | [Fact Dynamics](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/fact-dynamics.mdx), [TruthTracer](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/truth-tracer.mdx), and [UnCovered](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/uncovered.mdx) | One maintained multimodal fact-checking recipe is more useful than three overlapping showcase pages. |

## Full removal manifest

### Sonar examples

- [Daily Knowledge Bot](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/daily-knowledge-bot)
- [Perplexity Discord Bot](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/discord-py-bot)
- [Disease Information App](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/disease-qa)
- [Fact Checker CLI](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/fact-checker-cli)
- [Financial News Tracker](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/financial-news-tracker)
- [Academic Research Finder CLI](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/research-finder)

### Sonar guides

- [Memory Management overview](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/memory-management/README.mdx)
- [Chat Summary Memory Buffer](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/memory-management/chat-summary-memory-buffer)
- [Persistent Chat Memory](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/memory-management/chat-with-persistence)
- [OpenAI Agents Integration](https://github.com/ppl-ai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/openai-agents-integration)

### Community showcase

All 26 showcase pages were removed. The recommended concepts above are the strongest candidates for first-party Agent API recipes. The remaining archived submissions are [Ellipsis](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/Ellipsis.mdx), [BazaarAISaathi](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/bazaar-ai-saathi.mdx), [Briefo](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/briefo.mdx), [CycleSyncAI](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/cycle-sync-ai.mdx), [Executive Intelligence](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/executive-intelligence.mdx), [FirstPrinciples](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/first-principle.mdx), [FlameGuardAI](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/flameguardai.mdx), [Flow & Focus](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/flow-and-focus.mdx), [Greenify](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/greenify.mdx), [Monday](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/monday.mdx), [MVP LifeLine](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/mvp-lifeline-ai-app.mdx), [Perplexity Client](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexity-client.mdx), [Perplexity Dart & Flutter SDKs](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexity-flutter.mdx), [Perplexity Lens](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexity-lens.mdx), and [Valetudo AI](https://github.com/ppl-ai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/valetudo-ai.mdx).

## Republish checklist

- Start from the current Agent API migration guide and API contract; do not publish the archived Sonar implementation.
- Use `responses.create` or `POST /v1/agent`, typed `output` items, and current preset/tool conventions.
- Add `products: [agent-api]` and controlled `categories` frontmatter.
- Test all runnable code against the live Agent API and record the proof before publication.
- Review third-party dependencies, repository activity, privacy implications, and safety-sensitive claims before presenting a community concept as a maintained first-party example.
