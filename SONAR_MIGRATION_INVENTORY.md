# Sonar cookbook migration inventory

This inventory records the 26 Community Showcase pages, 9 examples, and 6 guides reviewed before the September 27, 2026 end of public Sonar Chat Completions support. It distinguishes content that remains live from Sonar content removed now and ranks the concepts worth rebuilding on the Agent API.

The complete pre-removal source is preserved in [`api-cookbook` at `543c229`](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs). A prior docs commit, [`514a467a`](https://github.com/ppl-ai/api-docs/commit/514a467adff2b418d254ce3ecb22948b00baaab9), contains live-tested Agent API ports of the ten removed first-party pages. Treat those ports as recovery material, not publication-ready content: review them against the current Agent API contract before reuse. The later revert, [`b264aca7`](https://github.com/ppl-ai/api-docs/commit/b264aca7), preserves their history.

## Decision summary

- **Keep unchanged:** `equity-research-brief`, `model-comparison`, `search-news-monitor`, `langchain-vc-memo-agent`, and `multi-provider-orchestration`. These already use the Agent API or Search API, even where an Agent API example selects a `perplexity/sonar` model.
- **Rebuild first:** `fact-checker-cli`, `openai-agents-integration`, `discord-py-bot`, `financial-news-tracker`, and `daily-knowledge-bot`. Consolidate the three memory-management pages into one Agent API memory guide.
- **Rebuild later:** `perplexigrid`, `daily-news-briefing`, `perplexity-flutter`, `citypulse-ai-search`, and `greenify`.
- **Archive only:** the other 21 Community Showcase pages plus `disease-qa` and `research-finder`.
- **Remove now:** all 26 Community Showcase pages, all 6 Sonar examples, and all 4 Sonar guides. Git history and the links below preserve the deleted source.

## Content that remains live

These five pages are part of the 41-item audit but are not Sonar Chat Completions content.

| Item | Type | API surface | Decision |
| --- | --- | --- | --- |
| [Equity Research Brief](docs/examples/equity-research-brief/README.mdx) | Example | Agent API with `finance_search` | Keep unchanged; review its `perplexity/sonar` model choice only if that Agent API model ID is withdrawn. |
| [Model Comparison](docs/examples/model-comparison/README.mdx) | Example | Agent API model routing and fallback | Keep unchanged; it is the canonical comparison recipe. |
| [Search News Monitor](docs/examples/search-news-monitor/README.mdx) | Example | Search API | Keep unchanged; its only Sonar reference was the shared deprecation banner. |
| [LangChain VC Memo Agent](docs/articles/langchain-vc-memo-agent/README.mdx) | Guide | Agent API with `web_search` and `finance_search` | Keep unchanged; use it as the quality bar for framework integrations. |
| [Multi-provider Orchestration](docs/articles/multi-provider-orchestration/README.mdx) | Guide | Agent API model routing, fallback, comparison, and model discovery | Keep unchanged; it already covers the routing lesson attempted by several showcases. |

## Rebuild first

The order below follows the source-grounded audit. Rebuild the archived behavior as maintained, first-party Agent API content rather than mechanically replacing an endpoint or republishing community code.

| Order | Source material | Agent API capability to teach | Key migration concern |
| --- | --- | --- | --- |
| 1 | [Fact Checker CLI](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/fact-checker-cli) | Strict structured verdict/evidence output plus `web_search` source attribution. | Replace the Sonar model allowlist and JSON/text branching; keep the framing factual and avoid verdict-style claims about people. |
| 2 | [OpenAI Agents integration](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/openai-agents-integration) | OpenAI-compatible framework interop, function calling, and custom tools on the Agent API. | Revalidate against the current OpenAI Agents SDK and current Agent API model IDs. |
| 3 | [Discord bot](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/discord-py-bot) | Long-running chat integration, streaming or chunked delivery, and per-user request handling. | Rewrite both Chat Completions call sites and preserve Discord's 2,000-character response handling. |
| 4 | [Memory Management hub](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/memory-management/README.mdx) | Agent API conversation state as the default answer to context-window loss. | Merge the hub and both child recipes into one guide instead of restoring a three-page tree. |
| 5 | [Chat Summary Memory Buffer](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/memory-management/chat-summary-memory-buffer) | Token-budgeted summarize-and-truncate memory as a manual fallback. | Remove Sonar-specific message conversion and avoid making LlamaIndex the only path. |
| 6 | [Persistent Chat Memory](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/articles/memory-management/chat-with-persistence) | Durable cross-session memory with vector retrieval of prior turns. | Distinguish conversation memory from the existing embeddings/RAG guide and revalidate LanceDB/LlamaIndex APIs. |
| 7 | [Financial News Tracker](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/financial-news-tracker) | `finance_search`, structured outputs, and recency windows for topic-level market monitoring. | Keep it distinct from per-ticker briefs and SEC search; frame output as analysis, not investment advice. |
| 8 | [Daily Knowledge Bot](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/daily-knowledge-bot) | Scheduled automation that writes dated file artifacts with retries. | Preserve the scheduling shell while replacing the Sonar request and response parsing. |

Items 1–3 and 7–8 already have Perplexity-owned runnable code. Items 4–6 are one rebuild project: a consolidated Agent API memory guide with native conversation state first, token-budget summarization second, and durable retrieval when cross-session recall is required.

## Rebuild later

| Source concept | Agent API lesson | Why it is later |
| --- | --- | --- |
| [PerplexiGrid](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexigrid.mdx) | Generate a validated visualization specification that an application renders. | Strong structured-output story, but it needs a Perplexity-owned, Supabase-free rewrite and overlaps the existing Competitor Buzz Tracker. |
| [Daily News Briefing](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/daily-news-briefing.mdx) | Deliver a scheduled digest into an external knowledge tool such as Obsidian. | The community project is well maintained, but its sample uses the retired `sonar-medium-online` ID and the digest concept overlaps News Dedupe Digest. |
| [Perplexity Dart and Flutter SDKs](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexity-flutter.mdx) | Type-safe streaming and multimodal Agent API integration for mobile developers. | The third-party SDKs do not support Agent API and would need sponsorship or replacement. |
| [CityPulse](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/citypulse-ai-search.mdx) | Two-stage fast retrieval then reasoning with structured output. | It needs first-party code and a safe, reproducible location-data substitute; routing is already covered by retained recipes. |
| [Greenify](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/greenify.mdx) | Multimodal image input to schema-validated structured output. | Prefer extending the existing Image Analysis example with schema validation if that teaches the same capability. |

## Archive only

These pages do not merit a standalone Agent API rebuild. Their historical source remains available for reference.

### Community Showcase

| Item | Why it should stay archived |
| --- | --- |
| [4Point Hoops](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/4point-Hoops.mdx) | The reusable API portion is a thin prompt wrapper around scraped sports data in an unlicensed SaaS stack. |
| [Ellipsis](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/Ellipsis.mdx) | Most of its value and complexity is in third-party TTS and podcast distribution, not the Perplexity request. |
| [BazaarAISaathi](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/bazaar-ai-saathi.mdx) | Personalized investment recommendations create avoidable risk, and retained recipes already cover finance research and model routing. |
| [Briefo](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/briefo.mdx) | It is a consumer mobile product rather than a reproducible API pattern; research and memory are covered elsewhere. |
| [CycleSyncAI](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/cycle-sync-ai.mdx) | Personalized health guidance is risky, and the distinctive implementation is iOS HealthKit plumbing. |
| [Executive Intelligence](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/executive-intelligence.mdx) | The research and memory patterns duplicate maintained Agent API examples. |
| [Fact Dynamics](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/fact-dynamics.mdx) | Its fact-checking concept is better represented by the first-party CLI; the distinct part is third-party Flutter speech-to-text. |
| [FirstPrinciples](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/first-principle.mdx) | Its arbitrary two-provider split is superseded by native Agent API provider routing. |
| [FlameGuardAI](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/flameguardai.mdx) | Property fire-safety claims are risky, and the iterative research loop is now native Agent API behavior. |
| [Flow & Focus](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/flow-and-focus.mdx) | This is primarily a feed UI; fast-feed/deep-dive behavior overlaps the async deep-research guide. |
| [Monday](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/monday.mdx) | The immersive UI has no distinct API lesson, requires several external services, and its linked source repository is unavailable. |
| [MVP LifeLine](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/mvp-lifeline-ai-app.mdx) | Dual-persona prompting is a thin pattern, while the mental-health companion framing is risky. |
| [PerplexiCart](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexicart.mdx) | Prompted product research plus JSON duplicates retained structured-output content and relies on fragile shopping claims. |
| [Perplexity Client](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexity-client.mdx) | Its premise is a desktop GUI over Sonar model and parameter controls, so the product would need a wholesale redesign. |
| [Perplexity Lens](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/perplexity-lens.mdx) | The browser knowledge-graph UI is the product; the API usage is not a distinct reusable pattern. |
| [PosterLens](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/posterlens.mdx) | Medical interpretation and generated follow-up questions create risk; image analysis and academic search already survive as separate recipes. |
| [Sonar Chromium Browser](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/sonar-chromium-browser.mdx) | Maintaining a Chromium fork is disproportionate to the simple search and summarization API pattern. |
| [StarPlex](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/starplex.mdx) | Startup validation is prompt assembly over common research flows already covered by retained Agent API recipes. |
| [TruthTracer](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/truth-tracer.mdx) | It duplicates the first-party fact-checker and makes high-risk misinformation scoring claims. |
| [UnCovered](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/uncovered.mdx) | It duplicates fact-checking and browser-surface concepts without a distinct API capability. |
| [Valetudo AI](https://github.com/perplexityai/api-cookbook/blob/543c229320acf9204d47a3ff91f13349b57047be/docs/showcase/valetudo-ai.mdx) | Medical answer generation is a claim class that should not be restored as a showcase. |

### Examples

| Item | Why it should stay archived |
| --- | --- |
| [Disease Information App](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/disease-qa) | Medical claims require a new safety review, and the old implementation exposes an API key in generated client-side HTML. |
| [Academic Research Finder](https://github.com/perplexityai/api-cookbook/tree/543c229320acf9204d47a3ff91f13349b57047be/docs/examples/research-finder) | The retained Academic and Scholarly Search guide supersedes it; fold useful CLI ergonomics into that guide instead. |

## Audit coverage

This ledger accounts for all 41 reviewed pages.

| Type | Keep | Rebuild first | Rebuild later | Archive only | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Community Showcase | 0 | 0 | 5 | 21 | 26 |
| Examples | 3 | 4 | 0 | 2 | 9 |
| Guides | 2 | 4 | 0 | 0 | 6 |
| **Unique pages** | **5** | **8** | **5** | **23** | **41** |

## Consolidation rules

- Keep one claim-verification recipe: rebuild `fact-checker-cli`; do not restore Fact Dynamics, TruthTracer, or UnCovered.
- Merge the memory hub, summary buffer, and persistent-chat pages into one guide.
- Let News Dedupe Digest own the digest concept; rebuild Daily News Briefing only for third-party-tool delivery.
- Keep finance recipes separated by job: per-ticker brief, VC memo, and topic-level news monitoring.
- Let Multi-provider Orchestration and Model Comparison own model routing and fallback.
- Fold Research Finder into Academic and Scholarly Search rather than restoring a duplicate page.
- Extend Image Analysis with schema validation instead of rebuilding Greenify if that covers the same lesson.

## Republish checklist

- Start from the current Agent API migration guide and public API contract; do not publish the archived Sonar implementation unchanged.
- Use current `responses.create` or `POST /v1/agent` conventions, typed output items, presets, and tools.
- Preserve the reusable prompts, schemas, integration shell, and assets from the historical source while rewriting API-specific code.
- Add `products: [agent-api]` and controlled `categories` frontmatter.
- Test all runnable code against the live Agent API and retain redacted proof before publication.
- Review dependency activity, licensing, privacy, and safety-sensitive claims before adapting community material into a maintained first-party recipe.
