# Agent API workflows

Three Python examples use Perplexity Agent API custom functions with application-owned state.
They do not use hosted MCP approvals or a persistent hosted execution environment.

| Example | Run | Guide |
| --- | --- | --- |
| Data analyst | `python data_analyst.py --demo "Compare conversion in the two recorded weeks."` | [Tutorial](data-analyst.mdx) |
| Slack bot | `python slack_bot.py` | [Tutorial](slack-bot.mdx) |
| Incident agent | `python sre_agent.py --alert sample_alert.json` | [Tutorial](sre-agent.mdx) |

## Setup

Use Python 3.12 or later.
Run these commands from this directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export PERPLEXITY_API_KEY="YOUR_API_KEY"
```

Slack additionally requires `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, and `SLACK_CHANNEL_IDS`.
Follow its tutorial to install the app with the included manifest.
The analyst and incident examples run with local synthetic data.
No example executes a deployment.

## Checks

```bash
python -m unittest -v test_workflows
python smoke_live.py
```

Unit checks do not call external services.
The live smoke check incurs Agent API charges and saves exact request/response records to `.state/live-proof.json`, without credentials.
It uses simulated Slack transport and synthetic incident data.
A real Slack workspace check remains a separate integration step.

## State and limits

`agent_loop.py` validates function names and arguments, polls background responses, replays transcripts, and enforces a 12-request limit per invocation.
It converts assistant output messages to text before resubmitting them through the pinned SDK.
It does not depend on `previous_response_id` for function results.
SQLite stores checkpoints and proposals in `.state/`; the application, not the Agent API, owns this state.
These files contain model-visible data, so protect the directory and define a retention policy.

Use one process per state file.
Slack has one worker and a bounded in-memory queue; it does not recover queued work after a restart.
The examples do not persist active response IDs, compact long histories, authenticate remote operators, or coordinate concurrent decisions.
The tutorials describe the integration boundaries to address before shared production use.
