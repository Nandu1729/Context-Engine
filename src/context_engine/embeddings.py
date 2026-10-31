"""Optional semantic retrieval: a small embedder interface and ready-made adapters.

Keyword (BM25) retrieval needs the question to reuse the evidence's words. An
embedder maps text to meaning vectors so "retailer" can find "merchant". Pass one to
`assemble_context(..., embedder=...)` (or `MemoryStore.assemble`) to rank chunks by
`semantic_weight` x meaning score + (1 - weight) x keyword score.

Models load only when you construct an embedder; assembly never downloads anything.

    from context_engine.embeddings import Model2VecEmbedder
    embedder = Model2VecEmbedder()          # pip install 'context-engineering-core[semantic]'
"""

from collections import OrderedDict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

from .errors import ContractError

# minishlab/potion-base-8M (MIT): chosen by measurement on the reworded-question
# benchmark (docs/BENCHMARK_REPORT.md). Pinned for reproducible vectors.
DEFAULT_MODEL = "minishlab/potion-base-8M"
DEFAULT_REVISION = "bf8b056651a2c21b8d2565580b8569da283cab23"
DEFAULT_SEMANTIC_WEIGHT = 0.7
_CACHE_SIZE = 16384
_MAX_TEXT = 100_000


@runtime_checkable
class Embedder(Protocol):
    """`name` must change whenever vectors would change (model, revision, settings)."""

    name: str

    def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...

    def embed_query(self, text: str) -> Sequence[float]: ...


class FunctionEmbedder:
    """Wrap your own functions, e.g. a hosted embedding API you call and pay for."""

    def __init__(
        self,
        name: str,
        documents: Callable[[list[str]], Sequence[Sequence[float]]],
        query: Callable[[str], Sequence[float]] | None = None,
    ):
        if not isinstance(name, str) or not name.strip():
            raise ContractError("Embedder name is required")
        self.name = name
        self._documents = documents
        self._query = query or (lambda text: documents([text])[0])

    def embed_documents(self, texts):
        return self._documents(list(texts))

    def embed_query(self, text):
        return self._query(text)


class Model2VecEmbedder:
    """Static embeddings (Model2Vec); ~30 MB model, fast on CPU, no ONNX runtime."""

    def __init__(self, model: str = DEFAULT_MODEL, *, revision: str | None = DEFAULT_REVISION):
        """Downloads (once, then cached) the pinned model revision; a local path also works."""
        try:
            from huggingface_hub import snapshot_download
            from model2vec import StaticModel
        except ImportError:
            raise ImportError(
                "Model2VecEmbedder needs model2vec: "
                "pip install 'context-engineering-core[semantic]'"
            ) from None
        local = Path(model).is_dir()
        self.name = f"model2vec:{model}@{'local' if local else revision or 'latest'}"
        path = (
            model
            if local
            else snapshot_download(
                model, revision=revision, allow_patterns=["*.json", "*.safetensors"]
            )
        )
        self._model = StaticModel.from_pretrained(path, force_download=False)

    def embed_documents(self, texts):
        return self._model.encode(list(texts))

    def embed_query(self, text):
        return self._model.encode([text])[0]


class FastEmbedEmbedder:
    """ONNX transformer embeddings via fastembed (e.g. BAAI/bge-small-en-v1.5).

    More accurate on the reworded benchmark but much slower to index than the default.
    """

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5", **options):
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise ImportError(
                "FastEmbedEmbedder needs fastembed: "
                "pip install 'context-engineering-core[fastembed]'"
            ) from None
        self.name = f"fastembed:{model}"
        self._model = TextEmbedding(model, **options)

    def embed_documents(self, texts):
        return list(self._model.passage_embed(list(texts)))

    def embed_query(self, text):
        return next(iter(self._model.query_embed([text])))


def _unit(vectors, dimension: int | None = None) -> np.ndarray:
    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim != 2 or array.shape[1] == 0 or not np.all(np.isfinite(array)):
        raise ContractError("Embedder returned invalid vectors")
    if dimension is not None and array.shape[1] != dimension:
        raise ContractError("Embedder vector dimensions differ")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    return np.divide(array, norms, out=np.zeros_like(array), where=norms > 0)


# Process-wide cache of unit document vectors keyed by (embedder name, text): a chat
# loop re-embeds the same history on every call otherwise.
_VECTORS: OrderedDict[tuple[str, str], np.ndarray] = OrderedDict()


def document_vectors(embedder: Embedder, texts: Sequence[str]) -> np.ndarray:
    keys = [(embedder.name, text) for text in texts]
    missing = list(dict.fromkeys(t for k, t in zip(keys, texts, strict=True) if k not in _VECTORS))
    if missing:
        if any(len(t) > _MAX_TEXT for t in missing):
            raise ContractError("Text too long to embed")
        fresh = _unit(embedder.embed_documents(missing))
        if len(fresh) != len(missing):
            raise ContractError("Embedder returned the wrong number of vectors")
        for text, vector in zip(missing, fresh, strict=True):
            _VECTORS[(embedder.name, text)] = vector
            _VECTORS.move_to_end((embedder.name, text))
    result = np.stack([_VECTORS[k] for k in keys]) if keys else np.zeros((0, 1), np.float32)
    for key in keys:
        _VECTORS.move_to_end(key)
    while len(_VECTORS) > _CACHE_SIZE:
        _VECTORS.popitem(last=False)
    return result


def query_vector(embedder: Embedder, text: str, dimension: int) -> np.ndarray:
    return _unit([embedder.embed_query(text)], dimension)[0]


def _scaled(values: np.ndarray) -> np.ndarray:
    low, high = float(values.min()), float(values.max())
    return np.zeros_like(values) if high <= low else (values - low) / (high - low)


def hybrid_scores(
    semantic: np.ndarray, lexical: np.ndarray, weight: float = DEFAULT_SEMANTIC_WEIGHT
) -> np.ndarray:
    """Per-query min-max scaled fusion: weight x meaning + (1 - weight) x keyword."""
    return weight * _scaled(np.asarray(semantic, np.float64)) + (1 - weight) * _scaled(
        np.asarray(lexical, np.float64)
    )


def validate_semantic(embedder, weight) -> None:
    if not isinstance(embedder, Embedder) or not isinstance(getattr(embedder, "name", None), str):
        raise ContractError("embedder must provide name, embed_documents and embed_query")
    if type(weight) not in (int, float) or not 0 <= weight <= 1:
        raise ContractError("semantic_weight must be between 0 and 1")


__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_REVISION",
    "DEFAULT_SEMANTIC_WEIGHT",
    "Embedder",
    "FastEmbedEmbedder",
    "FunctionEmbedder",
    "Model2VecEmbedder",
    "hybrid_scores",
]
