"""`ChatMemory`: two-line persistent memory over `MemoryStore`, tested offline."""

import pytest

from context_engine import ChatMemory, adapters
from context_engine.errors import ContractError, MemoryConflict

NOTE = (
    "Meeting note {}: we reviewed the weekly schedule and the cafeteria menu, nothing else changed."
)


@pytest.fixture
def memory(tmp_path):
    memory = ChatMemory(tmp_path / "data" / "chat.sqlite", session="alice")
    memory.save("My parcel is in locker L-42.", "Got it: locker L-42.")
    for number in range(1, 41):
        memory.add("user", NOTE.format(number))
    return memory


def text(messages):
    return "\n".join(m["content"] for m in messages)


def test_context_recalls_an_old_fact_asked_with_other_words(memory):
    messages = memory.context("Which storage box holds my package?", budget=900)
    assert messages[0]["role"] == "system" and messages[-1]["role"] == "user"
    assert "L-42" in text(messages)
    assert "Meeting note 40" in text(messages)  # Recent turns stay in the window.
    assert "Meeting note 1:" not in text(messages)  # Old filler is dropped.


def test_context_fits_the_budget(memory):
    result = memory.assemble("Which storage box holds my package?", budget=900)
    assert result.diagnostics.estimate.estimated_tokens <= result.diagnostics.input_allowance
    assert adapters.openai_chat(result)["messages"] == memory.context(
        "Which storage box holds my package?", budget=900
    )


def test_memory_persists_across_instances(memory, tmp_path):
    again = ChatMemory(tmp_path / "data" / "chat.sqlite", session="alice")
    assert "L-42" in text(again.context("Which locker has my parcel?", budget=900))
    other = ChatMemory(tmp_path / "data" / "chat.sqlite", session="bob")
    assert "L-42" not in text(other.context("Which locker has my parcel?", budget=900))


def test_pins_are_always_included_and_replaceable(memory):
    memory.pin("preferred_name", "Ally")
    assert "Ally" in text(memory.context("What is the weather?", budget=900))
    memory.pin("preferred_name", "Alicia")
    messages = text(memory.context("What is the weather?", budget=900))
    assert "Alicia" in messages and "Ally" not in messages
    memory.forget(pin="preferred_name")
    assert "Alicia" not in text(memory.context("What is the weather?", budget=900))


def test_forget_turn_and_delete_session(memory):
    turn_id = memory.add("user", "My gym code is 7781.")
    assert "7781" in text(memory.context("gym code", budget=900))
    memory.forget(turn_id)
    assert "7781" not in text(memory.context("gym code", budget=900))
    memory.delete_session()
    with pytest.raises(MemoryConflict):
        memory.context("anything")


@pytest.mark.parametrize("embedder,found", [(None, False), ("builtin", True)])
def test_only_meaning_search_finds_a_question_sharing_no_words(tmp_path, embedder, found):
    memory = ChatMemory(tmp_path / "chat.sqlite", embedder=embedder)
    memory.add("user", "My parcel is in locker L-42.")
    for number in range(1, 41):
        memory.add("user", NOTE.format(number))
    messages = memory.context("Which storage box holds our package?", budget=900)
    assert ("L-42" in text(messages)) is found


@pytest.mark.parametrize(
    "call",
    [
        lambda m: m.add("system", "x"),
        lambda m: m.add("user", ""),
        lambda m: m.forget(),
        lambda m: m.forget("t-1", pin="k"),
    ],
)
def test_invalid_calls_are_rejected(tmp_path, call):
    with pytest.raises(ContractError):
        call(ChatMemory(tmp_path / "chat.sqlite"))


def test_invalid_session_is_rejected(tmp_path):
    with pytest.raises(ContractError):
        ChatMemory(tmp_path / "chat.sqlite", session="")


def test_retrieval_share_scales_with_budget(tmp_path):
    memory = ChatMemory(tmp_path / "chat.sqlite")
    assert memory.diverse_turns is True  # Default since D117.
    fingerprint = memory.assemble("x").diagnostics.config_fingerprint
    plain = ChatMemory(tmp_path / "plain.sqlite", diverse_turns=False)
    assert plain.assemble("x").diagnostics.config_fingerprint != fingerprint
    assert memory.budget.retrieval_reserve == 1200
    assert memory._retrieval(memory.budget).top_k == 13
    big = memory._budget(8000)
    assert (big.retrieval_reserve, memory._retrieval(big).top_k) == (3200, 35)


@pytest.mark.parametrize("share", [0, 0.9, "0.4", None])
def test_invalid_retrieval_share_is_rejected(tmp_path, share):
    with pytest.raises(ContractError):
        ChatMemory(tmp_path / "chat.sqlite", retrieval_share=share)
