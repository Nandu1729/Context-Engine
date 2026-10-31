"""FastAPI chat endpoint with one memory session per user (async, non-blocking).

Run (needs fastapi, uvicorn and httpx, e.g. the [service] extra):
    export OPENAI_API_KEY=...                  # read from the environment only
    uvicorn examples.fastapi_chat:app

    curl -X POST localhost:8000/chat -H 'content-type: application/json' \
         -d '{"user_id": "alice", "message": "My parcel is in locker L-42."}'

`user_id` is trusted here for brevity. In a real app take it from your
authentication, never from the request body.
"""

import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from context_engine import AsyncChatMemory

USER_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class ChatIn(BaseModel):
    user_id: str
    message: str


class ChatOut(BaseModel):
    reply: str
    retrieved_turns: int


async def openai_compatible(messages):
    """One async chat-completions call; the key comes only from OPENAI_API_KEY."""
    import httpx

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            + "/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={"model": os.environ.get("CHAT_MODEL", "gpt-4o-mini"), "messages": messages},
        )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def create_app(db=Path("chat-memory.sqlite"), model=openai_compatible, budget=3000):
    app, sessions = FastAPI(title="Chat with memory"), {}

    def memory_for(user_id):
        if not USER_ID.fullmatch(user_id):
            raise HTTPException(422, "user_id must be 1-64 letters, digits, '_' or '-'")
        if user_id not in sessions:
            sessions[user_id] = AsyncChatMemory(db, session=user_id, budget=budget)
        return sessions[user_id]

    @app.post("/chat", response_model=ChatOut)
    async def chat(body: ChatIn):
        if not body.message.strip():
            raise HTTPException(422, "message must not be empty")
        memory = memory_for(body.user_id)
        result = await memory.aassemble(body.message)
        reply = await model(result.request.to_wire()["messages"])
        await memory.asave(body.message, reply)
        return ChatOut(reply=reply, retrieved_turns=len(result.diagnostics.retrieved_turn_ids))

    return app


app = create_app()
