"""Temporary shim: client-side tool-calling round-trip for ChatPerplexity.

Section 2 drives a client-side function-tool loop (bind a search tool, let the
model emit tool_calls, feed results back as ToolMessages). The released
``langchain-perplexity`` (<= 1.3.1, i.e. the merged langchain-ai/langchain#37359)
cannot serialize that loop back to the API:

  * ``_convert_message_to_dict`` has no ``ToolMessage`` branch (raises
    ``TypeError: Got unknown type``) and its ``AIMessage`` branch silently drops
    ``tool_calls``;
  * ``_to_responses_payload`` forwards Chat-Completions-style dicts unchanged, but
    the Responses (Agent) API needs typed ``function_call`` / ``function_call_output``
    input items.

``langchain-openai`` already handles all of this; the Perplexity package was
modeled on it but never inherited the branches. Importing this module monkey-patches
both methods so the loop round-trips. Remove it once the upstream fix ships.
"""
from __future__ import annotations

import json

import langchain_perplexity.chat_models as _cm
from langchain_core.messages import AIMessage, ToolMessage

_orig_convert = _cm.ChatPerplexity._convert_message_to_dict
_orig_responses = _cm.ChatPerplexity._to_responses_payload


def _convert_message_to_dict(self, message):
    """Add the ToolMessage / AIMessage.tool_calls branches (mirrors langchain-openai)."""
    if isinstance(message, ToolMessage):
        return {"role": "tool", "content": message.content,
                "tool_call_id": message.tool_call_id}
    if isinstance(message, AIMessage):
        out = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            out["tool_calls"] = [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                for tc in message.tool_calls
            ]
        return out
    return _orig_convert(self, message)


def _to_responses_payload(self, message_dicts, params, *, user_set_keys=None):
    """Translate Chat-Completions tool turns into Responses-API typed input items."""
    payload = _orig_responses(self, message_dicts, params, user_set_keys=user_set_keys)
    translated = []
    for m in payload.get("input", []):
        if not isinstance(m, dict):
            translated.append(m)
        elif m.get("role") == "assistant" and m.get("tool_calls"):
            if m.get("content"):
                translated.append({"role": "assistant", "content": m["content"]})
            for tc in m["tool_calls"]:
                translated.append({"type": "function_call", "call_id": tc["id"],
                                   "name": tc["function"]["name"],
                                   "arguments": tc["function"]["arguments"]})
        elif m.get("role") == "tool":
            out = m["content"] if isinstance(m["content"], str) else json.dumps(m["content"])
            translated.append({"type": "function_call_output",
                               "call_id": m["tool_call_id"], "output": out})
        else:
            translated.append(m)
    payload["input"] = translated
    return payload


_cm.ChatPerplexity._convert_message_to_dict = _convert_message_to_dict
_cm.ChatPerplexity._to_responses_payload = _to_responses_payload
