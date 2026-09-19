import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from agent_loop import State, client
from data_analyst import Warehouse, create_demo
from slack_bot import SlackBot
from sre_agent import IncidentAgent


def main():
    parser = argparse.ArgumentParser(
        description="Run paid Agent API checks with synthetic data and no real Slack or deployment writes."
    )
    parser.add_argument("--output", default=".state/live-proof.json")
    args = parser.parse_args()
    proof = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sdk": "perplexityai==0.43.5",
        "endpoint": "https://api.perplexity.ai/v1/agent",
        "calls": [],
        "results": {},
    }
    try:
        with client() as real_api, tempfile.TemporaryDirectory() as directory:

            def record(method):
                def invoke(*args, **kwargs):
                    entry = {
                        "method": method,
                        "args": list(args),
                        "request": json.loads(json.dumps(kwargs)),
                    }
                    proof["calls"].append(entry)
                    response = getattr(real_api.responses, method)(*args, **kwargs)
                    entry["response"] = response.model_dump(
                        mode="json", exclude_none=True
                    )
                    return response

                return invoke

            api = SimpleNamespace(
                responses=SimpleNamespace(
                    **{name: record(name) for name in ("create", "retrieve", "cancel")}
                )
            )
            root = Path(directory)
            state = State(root / "state.sqlite")
            create_demo(root / "warehouse.sqlite")
            warehouse = Warehouse(
                root / "warehouse.sqlite",
                state,
                {"conversion": "SUM(paid) / SUM(signups)", "source": "Synthetic data."},
            )
            warehouse.remember(
                "For the executive summary, report the self_service segment separately."
            )
            proof["results"]["analyst"] = warehouse.answer(
                api,
                "Why did conversion fall between the two recorded weeks? Query actual counts and use the saved correction.",
                "smoke",
            )
            assert warehouse.queries, "The analyst did not query the database."
            reopened = Warehouse(
                root / "warehouse.sqlite",
                State(root / "state.sqlite"),
                warehouse.context,
            )
            proof["results"]["analyst_followup"] = reopened.answer(
                api,
                "What were the two overall conversion percentages from your last answer?",
                "smoke",
            )
            print(
                "PASS: analyst SQL, explicit memory, and persisted follow-up",
                flush=True,
            )

            slack = Mock()
            slack.chat_postMessage.return_value = {"ts": "2.0"}
            slack.conversations_history.return_value = {
                "messages": [
                    {
                        "ts": "1.0",
                        "text": "Launch decision: ship Friday after the security review. Owner: Alex.",
                    }
                ]
            }
            slack.chat_getPermalink.return_value = {
                "permalink": "https://example.slack.com/archives/C1/p10"
            }
            bot = SlackBot(api, slack, state, "T1", "B1", {"C1"})
            event = {
                "team_id": "T1",
                "event_id": "E1",
                "event": {
                    "type": "app_mention",
                    "user": "U1",
                    "channel": "C1",
                    "ts": "1.0",
                    "text": "<@B1> Search recent messages for the launch decision and cite its URL.",
                },
            }
            assert bot.accept(event)
            bot.process_one()
            assert slack.conversations_history.called, "The Slack agent did not search."
            answer = slack.chat_update.call_args.kwargs["text"]
            assert "https://example.slack.com/archives/C1/p10" in answer, answer
            proof["results"]["slack_with_simulated_transport"] = answer
            print("PASS: live Agent API with simulated Slack transport", flush=True)

            alert = json.loads(
                Path(__file__).with_name("sample_alert.json").read_text()
            )
            for approve in (True, False):
                incident = {**alert, "fingerprint": "live-smoke-" + str(approve)}
                pending = IncidentAgent(api, state).investigate(incident)
                assert pending["status"] == "awaiting_decision", pending
                proof["results"]["pending_" + str(approve)] = pending
                resumed = IncidentAgent(api, State(root / "state.sqlite"))
                for proposal in pending["pending"]:
                    decided = resumed.decide(
                        incident["fingerprint"], proposal["call_id"], approve
                    )
                assert decided["status"] == "reviewed", decided
                assert all(
                    not decision["executed"] for decision in decided["decisions"]
                )
                proof["results"]["decision_" + str(approve)] = decided
                print(
                    "PASS: persisted incident decision "
                    + str(approve)
                    + ", no deployment",
                    flush=True,
                )
    finally:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proof, indent=2))
        path.chmod(0o600)


if __name__ == "__main__":
    main()
