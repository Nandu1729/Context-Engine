"""Terminal chatbot with persistent memory, for any OpenAI-compatible API.

Run (needs the [provider] extra for httpx):
    export OPENAI_API_KEY=...                  # read from the environment only
    export OPENAI_BASE_URL=https://api.openai.com/v1   # or Groq, a local server, ...
    export CHAT_MODEL=gpt-4o-mini
    python examples/terminal_chat.py --session alice

Memory is stored in chat-memory.sqlite; quit with an empty line or Ctrl-D.
"""

import argparse
import os

from context_engine import ChatMemory


def openai_compatible(messages):
    """One chat-completions call; the key comes only from OPENAI_API_KEY."""
    import httpx

    response = httpx.post(
        os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        + "/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={"model": os.environ.get("CHAT_MODEL", "gpt-4o-mini"), "messages": messages},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def chat_turn(memory, model, user_text):
    messages = memory.context(user_text)
    reply = model(messages)
    memory.save(user_text, reply)
    return reply


def main(argv=None, *, model=openai_compatible, read=input, write=print):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="default")
    parser.add_argument("--db", default="chat-memory.sqlite")
    args = parser.parse_args(argv)
    memory = ChatMemory(args.db, session=args.session)
    while True:
        try:
            user_text = read("you> ").strip()
        except EOFError:
            break
        if not user_text:
            break
        write("bot> " + chat_turn(memory, model, user_text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
