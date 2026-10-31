"""Offline MCP prototype tests: JSON-RPC handling, tools over MemoryStore, stdio round trip."""

import json
import os
import subprocess
import sys

import pytest

from context_engine.mcp_server import PROTOCOL_VERSIONS, TOOLS, ContextServer
from context_engine.memory import MemoryStore


@pytest.fixture
def server(tmp_path):
    return ContextServer(MemoryStore(tmp_path / "data" / "memory.sqlite"), "local")


def rpc(server, method, params=None, ident=1):
    message = {"jsonrpc": "2.0", "id": ident, "method": method}
    if params is not None:
        message["params"] = params
    return server.handle(message)


def tool(server, name, **arguments):
    response = rpc(server, "tools/call", {"name": name, "arguments": arguments})
    result = response["result"]
    return json.loads(result["content"][0]["text"]), result["isError"]


def test_initialize_negotiates_version_and_lists_tools(server):
    init = rpc(server, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
    assert init["result"]["protocolVersion"] == "2025-06-18"
    assert init["result"]["capabilities"] == {"tools": {"listChanged": False}}
    unknown = rpc(server, "initialize", {"protocolVersion": "1999-01-01"})
    assert unknown["result"]["protocolVersion"] == PROTOCOL_VERSIONS[0]
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    names = [t["name"] for t in rpc(server, "tools/list")["result"]["tools"]]
    assert names == ["add_message", "pin_fact", "get_context", "forget"]
    assert all(t["inputSchema"]["type"] == "object" for t in TOOLS)
    assert rpc(server, "ping")["result"] == {}
    assert rpc(server, "resources/list")["error"]["code"] == -32601


def test_tools_store_pin_retrieve_and_forget_within_budget(server):
    for i in range(120):
        tool(
            server,
            "add_message",
            session="s1",
            role="user",
            content=f"Note {i}: crate {i} sits in bay B-{i}.",
        )
    pinned, error = tool(
        server, "pin_fact", session="s1", key="owner", value="Team Amber owns the bays."
    )
    assert not error and pinned == {"key": "owner", "revision": 1}
    assert (
        tool(server, "pin_fact", session="s1", key="owner", value="Team Blue")[0]["revision"] == 2
    )
    context, error = tool(
        server, "get_context", session="s1", question="Which bay holds crate 17?", budget=900
    )
    assert not error and context["estimated_tokens"] <= context["input_allowance"] == 900
    text = json.dumps(context["messages"])
    assert "B-17" in text and "Team Blue" in text and "Team Amber" not in text
    assert context["retrieved_turn_ids"] and context["omitted_turns"] > 0
    turn = context["retrieved_turn_ids"][0]
    assert tool(server, "forget", session="s1", kind="turn", key=turn)[0]["deleted"] == "turn"
    again, _ = tool(server, "get_context", session="s1", question="Which bay holds crate 17?")
    assert turn not in again["retrieved_turn_ids"] + again["kept_turn_ids"]
    assert tool(server, "forget", session="s1", kind="session")[0]["deleted"] == "session"
    gone, error = tool(server, "get_context", session="s1", question="?")
    assert error  # A deleted session cannot be silently recreated.


def test_sessions_are_isolated(server):
    tool(server, "add_message", session="a", role="user", content="Secret code is ALPHA-9.")
    other, _ = tool(server, "get_context", session="b", question="What is the secret code?")
    assert "ALPHA-9" not in json.dumps(other["messages"])


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("add_message", {"session": "s", "role": "system", "content": "x"}),
        ("add_message", {"session": "", "role": "user", "content": "x"}),
        ("get_context", {"session": "s", "question": "q", "budget": 10}),
        ("forget", {"session": "s", "kind": "everything"}),
    ],
)
def test_invalid_arguments_are_tool_errors_not_crashes(server, name, arguments):
    response = rpc(server, "tools/call", {"name": name, "arguments": arguments})
    assert response["result"]["isError"] is True


def test_protocol_errors(server):
    assert server.handle({"id": 1, "method": "ping"})["error"]["code"] == -32600
    assert rpc(server, "tools/call", {"name": "nope", "arguments": {}})["error"]["code"] == -32602
    assert rpc(server, "tools/call", {})["error"]["code"] == -32602


def test_required_context_too_large_is_reported_with_code_not_content(server):
    tool(server, "pin_fact", session="s", key="big", value="PRIVATE " * 400)
    result, error = tool(server, "get_context", session="s", question="q", budget=300)
    assert error and result["code"] and "PRIVATE" not in json.dumps(result)


def test_stdio_round_trip_in_subprocess(tmp_path):
    lines = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-11-25"},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "add_message",
                "arguments": {"session": "s", "role": "user", "content": "Dock is D-4."},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_context",
                "arguments": {"session": "s", "question": "Which dock?"},
            },
        },
    ]
    stdin = "\n".join(json.dumps(line) for line in lines) + "\nnot json\n"
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"PATH", "HOME", "TMPDIR", "TIKTOKEN_CACHE_DIR", "SYSTEMROOT"}
    }
    done = subprocess.run(
        [sys.executable, "-m", "context_engine.mcp_server", "--data-dir", str(tmp_path / "d")],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    responses = [json.loads(line) for line in done.stdout.splitlines()]
    assert [r.get("id") for r in responses] == [1, 2, 3, None]
    assert responses[0]["result"]["serverInfo"]["name"] == "context-engine"
    assert "D-4" in responses[2]["result"]["content"][0]["text"]
    assert responses[3]["error"]["code"] == -32700
