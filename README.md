A comprehensive collection of practical examples, integration guides, and community showcases for building with [Perplexity's Agent API](https://docs.perplexity.ai/docs/agent-api/quickstart) — the new primary API for building hosted agents with native web access, citations, code execution, subagents, and durable, long-running work.

> **Agent API is now the primary Perplexity API.** New projects should build on the Agent API. The Sonar API (`/chat/completions`) is deprecated — if you're on Sonar, see the [migrate from Sonar guide](https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar) to move to the Agent API.

📖 **[View the full cookbook →](https://docs.perplexity.ai/cookbook)**

## What's Inside

### 🛠️ [Examples](docs/examples/)
Ready-to-run applications demonstrating real-world use cases:

- **[Equity Research Brief](docs/examples/equity-research-brief/)** - Agent API + `finance_search` for ticker-level research briefs
- **[Finance Chart (Sandbox)](docs/examples/finance-chart-sandbox/)** - Agent API + `finance_search` + `sandbox` to chart a stock's price history
- **[Customer Enrichment with ClickHouse](docs/examples/customer-enrichment-agent-api/)** - Agent API + `people_search` + custom functions with append-only provenance
- **[Fact Checker CLI](docs/examples/fact-checker-cli/)** - Verify claims and articles for accuracy
- **[Daily Knowledge Bot](docs/examples/daily-knowledge-bot/)** - Automated daily fact delivery system  
- **[Disease Information App](docs/examples/disease-qa/)** - Interactive medical information lookup
- **[Financial News Tracker](docs/examples/financial-news-tracker/)** - Real-time market analysis
- **[Academic Research Finder](docs/examples/research-finder/)** - Literature discovery and summarization
- **[Discord Bot](docs/examples/discord-py-bot/)** - Discord integration example

### 🌟 [Community Showcase](docs/showcase/)
Community-built applications including:
- News and finance apps
- AI-powered search tools  
- Browser extensions
- Educational platforms
- And many more innovative projects

### 📚 [Integration Guides](docs/articles/)
In-depth tutorials for advanced implementations:
- Migrating from Sonar to the Agent API
- Memory management patterns
- OpenAI agents integration
- Multi-modal implementations

## Quick Start

1. **Browse the [documentation](https://docs.perplexity.ai/cookbook)** to find examples that match your needs
2. **Clone this repository** and navigate to any example directory
3. **Follow the setup instructions** in each example's README
4. **Get your API key** from [Perplexity](https://docs.perplexity.ai/guides/getting-started)
5. **Build and customize** for your specific use case

## API Key Setup

All examples require a Perplexity API key:

```bash
export PPLX_API_KEY="your-api-key-here"
```

Get your API key at [docs.perplexity.ai](https://docs.perplexity.ai/guides/getting-started).

## Contributing

Have a project built with the Agent API? We'd love to feature it! 

- **[Submit an Example Tutorial](CONTRIBUTING.md#for-examples)**
- **[Submit a Showcase Project](CONTRIBUTING.md#for-showcase-projects)**  
- **[View Full Contributing Guidelines](CONTRIBUTING.md)**

## Resources

- **[Agent API Documentation](https://docs.perplexity.ai/docs/agent-api/quickstart)**
- **[Migrate from Sonar](https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar)**
- **[API Playground](https://perplexity.ai/account/api/playground)**
- **[Cookbook Documentation](https://docs.perplexity.ai/cookbook)**

---

*This repository syncs to [docs.perplexity.ai/cookbook](https://docs.perplexity.ai/cookbook) on every commit.*
