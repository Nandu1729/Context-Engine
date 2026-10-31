"""AsyncChatMemory and the chat example apps, offline with fake models (no API calls)."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from context_engine import AsyncChatMemory
from examples import fastapi_chat, terminal_chat

FACT = "My parcel is in locker L-42."
QUESTION = "Which storage box holds our package?"


def test_async_memory_round_trip(tmp_path):
    async def run():
        memory = AsyncChatMemory(tmp_path / "chat.sqlite", session="alice")
        await memory.asave(FACT, "Noted.")
        await asyncio.gather(*(memory.aadd("user", f"Filler note {i}.") for i in range(30)))
        await memory.apin("name", "Alice")
        messages = await memory.acontext(QUESTION, budget=900)
        return memory, "\n".join(m["content"] for m in messages)

    memory, text = asyncio.run(run())
    assert "L-42" in text and "Alice" in text
    history = memory.store.snapshot(memory.scope).history
    assert len(history) == 32  # Concurrent writes are serialized, none lost.


def test_terminal_chat_uses_memory(tmp_path):
    seen = []

    def model(messages):
        seen.append("\n".join(m["content"] for m in messages))
        return "ok"

    inputs, output = iter([FACT, *(f"Unrelated note {i}." for i in range(30)), QUESTION, ""]), []
    code = terminal_chat.main(
        ["--db", str(tmp_path / "chat.sqlite"), "--session", "s"],
        model=model,
        read=lambda _: next(inputs),
        write=output.append,
    )
    assert code == 0 and output[-1] == "bot> ok"
    assert "L-42" in seen[-1]


def test_fastapi_chat_keeps_users_apart(tmp_path):
    seen = []

    async def model(messages):
        seen.append("\n".join(m["content"] for m in messages))
        return "ok"

    client = TestClient(fastapi_chat.create_app(tmp_path / "chat.sqlite", model=model))
    assert client.post("/chat", json={"user_id": "alice", "message": FACT}).status_code == 200
    reply = client.post("/chat", json={"user_id": "alice", "message": QUESTION})
    assert reply.json()["reply"] == "ok" and "L-42" in seen[-1]
    client.post("/chat", json={"user_id": "bob", "message": QUESTION})
    assert "L-42" not in seen[-1]


@pytest.mark.parametrize(
    "body", [{"user_id": "../x", "message": "hi"}, {"user_id": "alice", "message": " "}]
)
def test_fastapi_chat_rejects_bad_input(tmp_path, body):
    async def model(messages):
        raise AssertionError("model must not be called")

    client = TestClient(fastapi_chat.create_app(tmp_path / "chat.sqlite", model=model))
    assert client.post("/chat", json=body).status_code == 422


def test_examples_read_keys_only_from_environment():
    for module in (terminal_chat, fastapi_chat):
        source = open(module.__file__).read()
        assert "os.environ['OPENAI_API_KEY']" in source and "sk-" not in source
