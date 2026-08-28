# Sonar to Agent API cookbook backlog

This record preserves the useful ideas from Sonar-dependent cookbook content removed ahead of the [September 27, 2026 public-support deadline](https://github.com/ppl-ai/api-docs/blob/e19829338b975df351831342b5ef5c21ab255c83/snippets/SonarDeprecationNotice.mdx). Rebuild these recipes against the [Agent API](https://docs.perplexity.ai/docs/agent-api/quickstart); do not restore the old Chat Completions code.

The source links below are pinned to the last pre-cleanup revisions in [`api-cookbook`](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be) and [`api-docs`](https://github.com/ppl-ai/api-docs/tree/e19829338b975df351831342b5ef5c21ab255c83). The repositories had diverged, so both snapshots are needed to preserve every removed item.

## Prioritized rebuilds

| Priority | Recipe to build | Source material | Agent API direction |
| --- | --- | --- | --- |
| P0 | Equity research brief | [Equity Research Brief](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/equity-research-brief) | Keep the existing `finance_search` workflow, remove the `perplexity/sonar` quote profile, and use a non-Sonar model for every path. |
| P0 | Multi-provider comparison and routing | [Model Comparison](https://github.com/ppl-ai/api-docs/blob/e19829338b975df351831342b5ef5c21ab255c83/docs/cookbook/examples/model-comparison/README.mdx) and [Multi-Provider Orchestration](https://github.com/ppl-ai/api-docs/blob/e19829338b975df351831342b5ef5c21ab255c83/docs/cookbook/articles/multi-provider-orchestration/README.mdx) | Combine the overlapping recipes around Agent API third-party models, fallback behavior, cost, and latency. Replace the Sonar research route with a non-Sonar model plus `web_search`. |
| P0 | Citation-aware fact checker | [Fact Checker CLI](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/fact-checker-cli), [TruthTracer](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/truth-tracer.mdx), [UnCovered](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/uncovered.mdx), and [Fact Dynamics](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/fact-dynamics.mdx) | Build one maintained example using `web_search`, structured output, citations from response fields, and optional image input. |
| P0 | Conversation state and durable memory | [Memory Management](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/memory-management) | Replace the three LlamaIndex/Sonar pages with one guide that starts with Agent API [`previous_response_id`](https://docs.perplexity.ai/docs/agent-api/conversation-state) and then adds application-owned long-term storage only where needed. |
| P0 | Scientific poster research assistant | [PosterLens](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/posterlens.mdx) | Turn the showcase into a runnable image/file-input recipe that extracts claims, searches for supporting literature, and returns cited findings. |
| P0 | Generated analytics dashboard | [PerplexiGrid](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexigrid.mdx) | Rebuild as an Agent API [`sandbox`](https://docs.perplexity.ai/docs/agent-api/tools/sandbox) example that analyzes supplied data and returns a shareable chart or HTML artifact. |
| P1 | Academic literature finder | [Academic Research Finder CLI](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/research-finder) | Fold the useful CLI and schema pieces into the existing Agent API academic-search guide instead of publishing a second overlapping tutorial. |
| P1 | Financial-news monitor and digest | [Financial News Tracker](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/financial-news-tracker), [Daily News Briefing](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/daily-news-briefing.mdx), and [Flow & Focus](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/flow-and-focus.mdx) | Extend the retained Search API monitor or Agent API news-deduplication guide with `finance_search`, summarization, and a scheduled-delivery example. |
| P1 | Value-aligned shopping research | [PerplexiCart](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexicart.mdx) | Create a runnable Agent API recipe using web research, explicit user constraints, structured recommendations, and source-backed tradeoffs. |
| P1 | Local discovery assistant | [CityPulse](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/citypulse-ai-search.mdx) | Build a focused location-search recipe with structured place results and clear handling of user-provided location data. |
| P1 | OpenAI SDK migration pattern | [OpenAI Agents Integration](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/openai-agents-integration) | Replace the custom Sonar Chat Completions client with a concise Agent API/OpenAI Responses compatibility guide; avoid duplicating the Agent API quickstart. |

## Complete removal inventory

The items below are intentionally not separate rebuilds. Their useful parts are folded into a prioritized recipe above, already covered by a retained cookbook page, too generic to teach an API capability, or unsuitable as a first-party guide without substantial product and safety work.

### Guides and examples

| Removed item | Disposition |
| --- | --- |
| Chat Summary Memory Buffer | Fold into Conversation state and durable memory. |
| Persistent Chat Memory | Fold into Conversation state and durable memory. |
| Memory Management overview | Fold into Conversation state and durable memory. |
| Fact Checker CLI | Rebuild as Citation-aware fact checker. |
| Academic Research Finder CLI | Fold into the retained Academic and Scholarly Search guide. |
| Financial News Tracker | Fold into Financial-news monitor and digest. |
| Equity Research Brief | Rebuild without its Sonar model profile. |
| Multi-Provider Model Comparison | Combine with Multi-Provider Orchestration. |
| Multi-Provider Orchestration | Combine with Multi-Provider Model Comparison. |
| OpenAI Agents Integration | Replace with the narrower OpenAI SDK migration pattern. |
| Daily Knowledge Bot | Archive; it is a generic scheduled prompt and does not justify a dedicated recipe. |
| Perplexity Discord Bot | Archive; transport wiring dominates the example and Agent API usage would be generic. |
| Disease Information App | Archive; a first-party medical-answer example needs a separate safety and product review. |

### Community showcase

| Removed item | Disposition |
| --- | --- |
| 4Point Hoops | Covered by retained finance and sandbox examples. |
| BazaarAISaathi | Covered by retained finance examples; portfolio advice would need additional safety review. |
| Briefo | Fold into Financial-news monitor and digest. |
| CityPulse | Rebuild as Local discovery assistant. |
| Daily News Briefing | Fold into Financial-news monitor and digest. |
| Executive Intelligence | Covered by retained deep-research guides. |
| Fact Dynamics | Fold into Citation-aware fact checker. |
| Flow & Focus | Fold into Financial-news monitor and digest. |
| PerplexiCart | Rebuild as Value-aligned shopping research. |
| PerplexiGrid | Rebuild as Generated analytics dashboard. |
| PosterLens | Rebuild as Scientific poster research assistant. |
| TruthTracer | Fold into Citation-aware fact checker. |
| UnCovered | Fold into Citation-aware fact checker. |
| CycleSyncAI | Archive; health-plan guidance needs a separate safety and product review. |
| FlameGuardAI | Archive; wildfire-risk decisions need domain-specific validation beyond an API recipe. |
| Greenify | Archive; the core pattern overlaps the retained image-analysis example. |
| Valetudo AI | Archive; medical-answer guidance needs a separate safety and product review. |
| Ellipsis | Archive; podcast generation does not demonstrate a distinctive Perplexity API capability. |
| FirstPrinciples | Archive; roadmap generation is a generic prompting pattern. |
| Monday | Archive; the voice and 3D application stack dominates the API lesson. |
| MVP LifeLine | Archive; the broad product concept does not map to one reproducible API pattern. |
| Perplexity Client | Archive; a generic desktop Chat Completions client is the migration target, not a new recipe. |
| Perplexity Dart & Flutter SDKs | Archive; unofficial SDK maintenance belongs in its own repository. |
| Perplexity Lens | Archive; knowledge-graph and browser-extension plumbing dominate the API lesson. |
| Sonar Chromium Browser | Archive; it is coupled directly to the retired Sonar integration. |
| StarPlex | Archive; startup advice is already covered by retained deep-research patterns. |

## Rebuild acceptance criteria

A recreated item should:

- call the Agent API through `client.responses.create()` or `POST /v1/agent`/`POST /v1/responses`;
- use no Sonar model identifiers, Chat Completions calls, or Sonar-specific response parsing;
- teach one distinct, reproducible capability rather than restore a marketing showcase;
- include runnable code, prerequisites, expected output, cost/latency considerations where relevant, and limitations;
- use citations, tool outputs, file artifacts, and structured output from their documented response fields; and
- pass the cookbook and Agent API documentation review before publication.
