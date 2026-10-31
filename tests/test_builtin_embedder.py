"""Bundled potion-base-8M embedder: exact tokenizer, reference vectors, default hybrid."""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from context_engine import assemble_context
from context_engine.config import BudgetConfig
from context_engine.embeddings import BUILTIN, BuiltinEmbedder, default_embedder, resolve_embedder
from context_engine.models import KeyedPins, Message, Role, Scope, Turn

DATA = Path(__file__).resolve().parents[1] / "src/context_engine/embedding_data"
# Token IDs from Hugging Face `tokenizers` (model's tokenizer.json, no special tokens).
REFERENCE_IDS = {
    "The merchant involved was merchant-aurora.": [1002, 5438, 1926, 1007, 5438, 17, 12164, 18],
    "Naïve café — İstanbul ΣΊΣΥΦΟΣ straße": [
        14749,
        6674,
        523,
        8966,
        179,
        17205,
        28739,
        28741,
        28742,
        28736,
        28739,
        1364,
        26813,
    ],
    "中文 mixed 日本語 text": [752, 867, 2822, 870, 882, 956, 2799],
    "tab\tnew\nline\x00ctrl e-mail: a.b@c.d (x)!?": [
        20634,
        1053,
        1246,
        5599,
        11196,
        47,
        17,
        4659,
        30,
        43,
        18,
        44,
        36,
        45,
        18,
        46,
        12,
        66,
        13,
        5,
        35,
    ],
    "supercalifragilisticexpialidocious_42": [
        2571,
        8295,
        9134,
        28187,
        23417,
        3594,
        9294,
        18318,
        20279,
        9091,
        5319,
        41,
        3419,
    ],
}
# First six dimensions of model2vec 0.10 StaticModel.encode (float32 model).
REFERENCE_VECTOR = [-0.058, 0.1317, 0.0377, -0.0369, 0.0563, 0.0926]


@pytest.fixture(scope="module")
def embedder():
    return default_embedder()


def test_bundled_data_is_the_pinned_artifact():
    digests = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.iterdir() if p.is_file()
    }
    assert digests["potion-base-8M-int8.npz"].startswith("beb136058fd220c1")
    assert digests["potion-base-8M-vocab.txt"].startswith("1394523a67ddd404")
    assert "MIT" in (DATA / "LICENSE").read_text()


@pytest.mark.parametrize("text,ids", REFERENCE_IDS.items())
def test_tokenizer_matches_reference(embedder, text, ids):
    assert embedder._tokenizer.encode(text) == ids


def test_vector_matches_reference_model(embedder):
    vector = np.asarray(embedder.embed_query("Which retailer or seller took part?"))
    assert np.allclose(vector[:6], REFERENCE_VECTOR, atol=2e-3)
    assert abs(np.linalg.norm(vector) - 1) < 1e-5


def test_meaning_similarity_and_edge_cases(embedder):
    merchant, retailer, telemetry = (
        np.asarray(embedder.embed_query(t)) for t in ("merchant", "retailer", "telemetry")
    )
    assert merchant @ retailer > merchant @ telemetry
    assert not np.any(embedder.embed_query("\x00\x01"))  # Nothing to embed: zero vector.
    assert embedder.embed_documents([]).shape[0] == 0
    long = "word " * 5000
    assert np.isfinite(embedder.embed_query(long)).all()


def test_default_is_builtin_and_none_is_keyword_only():
    assert resolve_embedder(BUILTIN) is default_embedder() and resolve_embedder(None) is None
    assert isinstance(default_embedder(), BuiltinEmbedder)
    scope = Scope("t", "c")
    notes = [f"Note {i}: routine status check, nothing new." for i in range(120)]
    notes[37] = "Note 37: the merchant involved was merchant-aurora."
    history = [Turn(f"t{i}", scope, (Message(f"m{i}", Role.USER, n),)) for i, n in enumerate(notes)]
    ask = dict(system="Answer.", at=None)
    default = assemble_context(
        history,
        "Which retailer or seller took part?",
        KeyedPins(scope),
        BudgetConfig(input_cap=900),
        **ask,
    )
    keyword = assemble_context(
        history,
        "Which retailer or seller took part?",
        KeyedPins(scope),
        BudgetConfig(input_cap=900),
        embedder=None,
        **ask,
    )
    assert "t37" in default.diagnostics.retrieved_turn_ids
    assert "t37" not in keyword.diagnostics.retrieved_turn_ids
    assert default.diagnostics.config_fingerprint != keyword.diagnostics.config_fingerprint
