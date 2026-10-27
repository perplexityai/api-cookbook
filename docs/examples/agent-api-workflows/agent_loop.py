import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from perplexity import (
    APIConnectionError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from slack_sdk.errors import SlackClientError


class State:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
        self.path.chmod(0o600)

    def read(self, key, default=None):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT value FROM records WHERE key = ?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else default

    def write(self, key, value):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO records VALUES (?, ?)", (key, json.dumps(value))
            )

    def claim(self, key):
        with closing(sqlite3.connect(self.path)) as db, db:
            return (
                db.execute(
                    "INSERT OR IGNORE INTO records VALUES (?, 'true')", (key,)
                ).rowcount
                == 1
            )

    def items(self, prefix):
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute(
                "SELECT key, value FROM records WHERE substr(key, 1, ?) = ?",
                (len(prefix), prefix),
            ).fetchall()
        return [(key, json.loads(value)) for key, value in rows]


def client():
    from perplexity import Perplexity

    return Perplexity(timeout=90, max_retries=0)


def function(name, description, **fields):
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {
                key: {"type": "string", "description": value}
                for key, value in fields.items()
            },
            "required": list(fields),
            "additionalProperties": False,
        },
        "strict": True,
    }


def arguments(call, definition):
    value = json.loads(call["arguments"])
    fields = definition["parameters"]["properties"]
    if not isinstance(value, dict) or value.keys() != fields.keys():
        raise ValueError("Invalid function arguments.")
    if any(
        not isinstance(item, str) or not item.strip() or len(item) > 12000
        for item in value.values()
    ):
        raise ValueError(
            "Function arguments must be nonempty strings of at most 12000 characters."
        )
    return value


def tool_result(call, value):
    return {
        "type": "function_call_output",
        "call_id": call["call_id"],
        "output": json.dumps(value),
    }


def run(
    api,
    history,
    instructions,
    tools,
    handlers,
    checkpoint=lambda history: None,
    stopped=lambda: False,
):
    definitions = {tool["name"]: tool for tool in tools}
    history = list(history)
    for _ in range(12):
        if stopped():
            raise InterruptedError("Stopped before the next API request.")
        response = api.responses.create(
            model=os.environ.get("AGENT_MODEL", "openai/gpt-5.6-sol"),
            instructions=instructions,
            tools=tools,
            input=history,
            max_output_tokens=3000,
            background=True,
        )
        deadline = time.monotonic() + 180
        cancellation_deadline = None
        while response.status in {"queued", "in_progress"}:
            if (
                stopped() or time.monotonic() > deadline
            ) and cancellation_deadline is None:
                try:
                    api.responses.cancel(response.id)
                except BadRequestError:
                    response = api.responses.retrieve(response.id)
                    if response.status in {"queued", "in_progress"}:
                        raise
                    break
                cancellation_deadline = time.monotonic() + 30
            if (
                cancellation_deadline is not None
                and time.monotonic() > cancellation_deadline
            ):
                raise TimeoutError(
                    "Cancellation is unconfirmed. Inspect response " + response.id
                )
            time.sleep(1)
            try:
                response = api.responses.retrieve(response.id)
            except (APIConnectionError, InternalServerError, RateLimitError):
                if time.monotonic() > deadline:
                    raise
        if response.status == "cancelled" or stopped():
            raise InterruptedError("The current task was stopped.")
        body = response.model_dump(mode="json", exclude_none=True)
        if body.get("status") != "completed":
            raise RuntimeError(
                "Agent response did not complete: " + str(body.get("status"))
            )
        output = body.get("output", [])
        calls = [item for item in output if item["type"] == "function_call"]
        if len({call["call_id"] for call in calls}) != len(calls):
            raise ValueError("Duplicate function call IDs.")
        for item in output:
            if item["type"] == "message":
                message_text = "\n".join(
                    part["text"]
                    for part in item.get("content", [])
                    if part["type"] == "output_text"
                )
                history.append(
                    {"type": "message", "role": "assistant", "content": message_text}
                )
            else:
                history.append(item)
        pending = []
        for call in calls:
            if call["name"] not in definitions:
                raise ValueError("The model requested an unregistered function.")
            try:
                args = arguments(call, definitions[call["name"]])
            except (ValueError, KeyError, TypeError):
                history.append(
                    tool_result(call, {"error": "Invalid function arguments."})
                )
                continue
            if call["name"] not in handlers:
                pending.append(call)
                continue
            if stopped():
                history.append(
                    tool_result(call, {"error": "The user stopped this task."})
                )
                continue
            try:
                result = handlers[call["name"]](**args)
            except (sqlite3.Error, SlackClientError, ValueError, TypeError, KeyError):
                result = {
                    "error": "Tool failed. Check its inputs and access permissions."
                }
            history.append(tool_result(call, result))
        checkpoint(history)
        text = "\n".join(
            part["text"]
            for item in output
            if item["type"] == "message"
            for part in item.get("content", [])
            if part["type"] == "output_text"
        )
        if pending or not calls:
            if not pending and not text:
                raise RuntimeError("The agent returned no answer.")
            return {"history": history, "pending": pending, "answer": text}
    raise RuntimeError("The function loop reached its 12-request limit.")
