import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from agent_loop import State, function, run
from data_analyst import Warehouse, create_demo
from perplexity import APIConnectionError, BadRequestError
from perplexity.generated.api import ResponsesRequestInput
from slack_bot import SlackBot
from sre_agent import IncidentAgent


def output(*items):
    body = {"id": "resp_test", "status": "completed", "output": list(items)}
    return SimpleNamespace(status="completed", model_dump=lambda **kwargs: body)


def message(text):
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }


def call(name, call_id="call_1", **args):
    return {
        "type": "function_call",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(args),
    }


def api_with(*responses):
    responses = iter(responses)

    def create(**kwargs):
        ResponsesRequestInput.model_validate(kwargs)
        return next(responses)

    return SimpleNamespace(responses=SimpleNamespace(create=Mock(side_effect=create)))


class WorkflowsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.state = State(self.root / "state.sqlite")

    def test_read_only_queries_limits_and_explicit_memory(self):
        path = self.root / "warehouse.sqlite"
        create_demo(path)
        warehouse = Warehouse(path, self.state, {"rate": "paid / signups"})
        result = warehouse.query_warehouse(
            "SELECT week, SUM(paid) FROM weekly_funnel GROUP BY week ORDER BY week"
        )
        self.assertEqual(result["rows"], [("2026-08-31", 100), ("2026-09-07", 60)])
        for query in [
            "DELETE FROM weekly_funnel",
            "PRAGMA query_only=OFF",
            "ATTACH DATABASE ':memory:' AS other",
            "SELECT load_extension('bad')",
            "SELECT 1; DELETE FROM weekly_funnel",
        ]:
            with self.subTest(query=query), self.assertRaises(sqlite3.Error):
                warehouse.query_warehouse(query)
        result = warehouse.query_warehouse(
            "WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x WHERE n<150) SELECT n FROM x"
        )
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["rows"]), 100)
        warehouse.remember("Use enterprise only for the enterprise conversion metric.")
        reopened = Warehouse(path, State(self.root / "state.sqlite"), {})
        self.assertEqual(
            len(reopened.search_context("enterprise")["saved_corrections"]), 1
        )

    def test_function_loop_replays_results_and_rejects_injected_arguments(self):
        api = api_with(
            output(call("lookup", channel="other", query="launch")),
            output(call("lookup", "call_2", query="launch")),
            output(message("Found it.")),
        )
        handler = Mock(return_value={"text": "launch decision"})
        result = run(
            api,
            [
                {
                    "type": "message",
                    "role": "user",
                    "content": "Find the launch decision.",
                }
            ],
            "Use lookup.",
            [function("lookup", "Search.", query="Search text.")],
            {"lookup": handler},
        )
        handler.assert_called_once_with(query="launch")
        self.assertEqual(result["answer"], "Found it.")
        results = [
            item
            for item in result["history"]
            if item.get("type") == "function_call_output"
        ]
        self.assertIn("error", json.loads(results[0]["output"]))
        self.assertEqual(json.loads(results[1]["output"]), {"text": "launch decision"})

    def test_slack_scoping_deduplication_followup_and_stop(self):
        slack = Mock()
        slack.chat_postMessage.return_value = {"ts": "2.0"}
        slack.conversations_history.return_value = {
            "messages": [{"ts": "1.0", "text": "Launch is Friday."}]
        }
        slack.chat_getPermalink.return_value = {
            "permalink": "https://example.slack.com/archives/C1/p10"
        }
        api = api_with(
            output(call("search_channel", query="launch")),
            output(message("Launch is Friday.")),
            output(message("Friday, as discussed.")),
        )
        bot = SlackBot(api, slack, self.state, "T1", "B1", {"C1"})
        event = {
            "team_id": "T1",
            "event_id": "E1",
            "event": {
                "type": "app_mention",
                "user": "U1",
                "channel": "C1",
                "ts": "1.0",
                "text": "<@B1> Find the launch decision.",
            },
        }
        self.assertFalse(bot.accept({**event, "team_id": "T2"}))
        self.assertFalse(
            bot.accept({**event, "event": {**event["event"], "channel": "C2"}})
        )
        self.assertTrue(bot.accept(event))
        self.assertFalse(bot.accept(event))
        bot.process_one()
        followup = {
            **event,
            "event_id": "E2",
            "event": {
                **event["event"],
                "ts": "3.0",
                "thread_ts": "1.0",
                "text": "<@B1> Which day?",
            },
        }
        self.assertTrue(bot.accept(followup))
        bot.process_one()
        slack.conversations_history.assert_called_once_with(channel="C1", limit=100)
        self.assertEqual(
            slack.chat_update.call_args.kwargs["text"], "Friday, as discussed."
        )
        ResponsesRequestInput.model_validate(
            {"input": self.state.read("slack:T1:C1:1.0")}
        )
        self.assertIn("Friday", json.dumps(self.state.read("slack:T1:C1:1.0")))
        self.assertIsNone(self.state.read("slack:T1:C2:1.0"))
        with self.assertRaises(PermissionError):
            bot.search("C2", "*")
        bot.accept({**followup, "event_id": "E3"})
        bot.accept(
            {
                **followup,
                "event_id": "E4",
                "event": {**followup["event"], "text": "<@B1> stop"},
            }
        )
        bot.process_one()
        self.assertEqual(api.responses.create.call_count, 3)

    def test_active_stop_cancels_and_does_not_dispatch_tools(self):
        api = api_with()
        api.responses.create.return_value = SimpleNamespace(
            id="resp_running", status="in_progress"
        )
        api.responses.create.side_effect = None
        api.responses.cancel = Mock()
        api.responses.retrieve = Mock(
            return_value=output(call("lookup", query="launch"))
        )
        handler = Mock()
        with patch("agent_loop.time.sleep"), self.assertRaises(InterruptedError):
            run(
                api,
                [],
                "Search.",
                [function("lookup", "Search.", query="Text.")],
                {"lookup": handler},
                stopped=Mock(side_effect=[False, True, True]),
            )
        api.responses.cancel.assert_called_once_with("resp_running")
        handler.assert_not_called()

    def test_function_loop_has_a_request_limit(self):
        api = api_with(
            *(output(call("lookup", f"call_{i}", query="launch")) for i in range(12))
        )
        with self.assertRaisesRegex(RuntimeError, "12-request limit"):
            run(
                api,
                [],
                "Search.",
                [function("lookup", "Search.", query="Text.")],
                {"lookup": lambda query: []},
            )
        self.assertEqual(api.responses.create.call_count, 12)

    def test_poll_connection_failure_retries_the_same_response(self):
        api = api_with()
        api.responses.create.side_effect = None
        api.responses.create.return_value = SimpleNamespace(
            id="resp_running", status="in_progress"
        )
        api.responses.retrieve = Mock(
            side_effect=[
                APIConnectionError(
                    request=httpx.Request("GET", "https://example.test")
                ),
                output(message("Done.")),
            ]
        )
        with patch("agent_loop.time.sleep"):
            result = run(api, [], "Answer.", [], {})
        self.assertEqual(result["answer"], "Done.")
        api.responses.create.assert_called_once()
        self.assertEqual(api.responses.retrieve.call_count, 2)

    def test_stop_racing_with_completion_does_not_execute_tools(self):
        api = api_with()
        api.responses.create.side_effect = None
        api.responses.create.return_value = SimpleNamespace(
            id="resp_running", status="in_progress"
        )
        api.responses.cancel = Mock(
            side_effect=BadRequestError(
                "already terminal",
                response=httpx.Response(
                    400, request=httpx.Request("POST", "https://example.test")
                ),
                body=None,
            )
        )
        api.responses.retrieve = Mock(
            return_value=output(call("lookup", query="launch"))
        )
        handler = Mock()
        with self.assertRaises(InterruptedError):
            run(
                api,
                [],
                "Search.",
                [function("lookup", "Search.", query="Text.")],
                {"lookup": handler},
                stopped=Mock(side_effect=[False, True, True]),
            )
        api.responses.cancel.assert_called_once_with("resp_running")
        handler.assert_not_called()

    def test_approval_survives_restart_and_never_executes_a_rollback(self):
        alert = json.loads(Path(__file__).with_name("sample_alert.json").read_text())
        for approve in (True, False):
            with self.subTest(approve=approve):
                alert = {**alert, "fingerprint": "incident-" + str(approve)}
                api = api_with(
                    output(
                        call(
                            "propose_rollback",
                            service=alert["service"],
                            target_version=alert["previous_version"],
                            reason="deploy-1 and log-1",
                        )
                    ),
                    output(message("Decision recorded. No deployment executed.")),
                )
                agent = IncidentAgent(api, self.state)
                pending = agent.investigate(alert)
                self.assertEqual(pending["status"], "awaiting_decision")
                self.assertEqual(agent.investigate(alert), pending)
                self.assertEqual(api.responses.create.call_count, 1)
                restarted = IncidentAgent(api, State(self.root / "state.sqlite"))
                with self.assertRaises(ValueError):
                    restarted.decide(alert["fingerprint"], "wrong-call", approve)
                result = restarted.decide(alert["fingerprint"], "call_1", approve)
                self.assertEqual(result["status"], "reviewed")
                self.assertFalse(result["decisions"][0]["executed"])
                self.assertEqual(
                    result["decisions"][0]["decision"],
                    "approved" if approve else "denied",
                )
                with self.assertRaises(ValueError):
                    restarted.decide(alert["fingerprint"], "call_1", approve)

    def test_resolved_and_mismatched_incidents_cannot_be_approved(self):
        alert = json.loads(Path(__file__).with_name("sample_alert.json").read_text())
        api = api_with(
            output(
                call(
                    "propose_rollback",
                    service=alert["service"],
                    target_version=alert["previous_version"],
                    reason="deploy-1",
                )
            )
        )
        agent = IncidentAgent(api, self.state)
        agent.investigate(alert)
        agent.resolve(alert["fingerprint"])
        with self.assertRaises(ValueError):
            agent.decide(alert["fingerprint"], "call_1", True)
        bad_api = api_with(
            output(
                call(
                    "propose_rollback",
                    service="other-service",
                    target_version="unknown",
                    reason="unsupported",
                )
            )
        )
        bad_agent = IncidentAgent(bad_api, self.state)
        with self.assertRaises(ValueError):
            bad_agent.investigate({**alert, "fingerprint": "mismatch"})
        self.assertEqual(self.state.read("incident:mismatch")["status"], "failed")


if __name__ == "__main__":
    unittest.main()
