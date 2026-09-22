"""BM25+ over original text chunks, excluding the shared planned recent window."""

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, replace

from rank_bm25 import BM25Plus

from ..config import RetrievalConfig
from ..context import ContextCarrier, LayerDiagnostic
from ..errors import MemoryIntegrityError
from ..models import BlockKind, Chunk, ContextBlock, SourceRef, Turn, canonical_json
from ..tokens import TokenCounter
from .common import fits_block, history_digest, plan_window, set_block


@dataclass(frozen=True)
class ChunkIndex:
    history_fingerprint: str
    config_fingerprint: str
    chunks: tuple[Chunk, ...]

    def validate(self, history, config):
        expected = hashlib.sha256(canonical_json(asdict(config)).encode()).hexdigest()
        if (
            self.history_fingerprint != history_digest(history)
            or self.config_fingerprint != expected
        ):
            raise MemoryIntegrityError("Chunk index history or configuration is stale")
        originals = {t.turn_id: t for t in history}
        if (
            not isinstance(self.chunks, tuple)
            or any(not isinstance(c, Chunk) for c in self.chunks)
            or len({c.chunk_id for c in self.chunks}) != len(self.chunks)
        ):
            raise MemoryIntegrityError("Invalid chunk index entries")
        for chunk in self.chunks:
            if not isinstance(chunk, Chunk) or chunk.source.turn_id not in originals:
                raise MemoryIntegrityError("Chunk index contains unknown source")
            chunk.validate_source(originals[chunk.source.turn_id])


def lexical_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return re.findall(r"\w+(?:[-.]\w+)*", normalized)


def chunk_turns(turns: tuple[Turn, ...], config: RetrievalConfig) -> tuple[Chunk, ...]:
    chunks = []
    version = f"characters-v1:{config.chunk_characters}:{config.overlap_characters}"
    stride = config.chunk_characters - config.overlap_characters
    for turn in turns:
        for message in turn.messages:
            message_hash = message.content_hash
            for start in range(0, len(message.content), stride):
                end = min(len(message.content), start + config.chunk_characters)
                content = message.content[start:end]
                if content.strip():
                    source = SourceRef(
                        turn.scope,
                        turn.turn_id,
                        message.message_id,
                        turn.revision,
                        start,
                        end,
                        message_hash,
                    )
                    identifier = hashlib.sha256(
                        canonical_json([asdict(source), version]).encode()
                    ).hexdigest()
                    chunks.append(Chunk(identifier, source, content, version))
                if end == len(message.content):
                    break
    return tuple(chunks)


def evidence_block(chunks: tuple[Chunk, ...], counter: TokenCounter) -> ContextBlock:
    content = (
        canonical_json(
            [
                {
                    "turn": c.source.turn_id,
                    "message": c.source.message_id,
                    "start": c.source.start,
                    "end": c.source.end,
                    "text": c.content,
                }
                for c in chunks
            ]
        )
        if chunks
        else ""
    )
    return ContextBlock(
        BlockKind.RETRIEVED,
        content,
        sources=tuple(c.source for c in chunks),
        text_tokens=counter.count_text(content),
    )


def overlaps(left: Chunk, right: Chunk) -> bool:
    a, b = left.source, right.source
    return (a.scope, a.turn_id, a.message_id, a.revision) == (
        b.scope,
        b.turn_id,
        b.message_id,
        b.revision,
    ) and max(a.start, b.start) < min(a.end, b.end)


@dataclass(frozen=True)
class RetrieveLayer:
    counter: TokenCounter
    config: RetrievalConfig = RetrievalConfig()
    chunk_index: ChunkIndex | None = None

    def apply(self, context: ContextCarrier) -> ContextCarrier:
        if self.chunk_index is not None:
            if not isinstance(self.chunk_index, ChunkIndex):
                raise MemoryIntegrityError("Expected a validated chunk index")
            self.chunk_index.validate(context.original_turns, self.config)
        planned = plan_window(context, self.counter)
        old = tuple(
            t for t in planned.original_turns if t.turn_id not in planned.plan.window_turn_ids
        )
        query = sorted(set(lexical_tokens(planned.question.content)))
        selected: tuple[Chunk, ...] = ()
        reason = "no_match"
        if not query:
            reason = "empty_query"
        elif not old:
            reason = "no_old_history"
        elif planned.plan.retrieval_tokens == 0:
            reason = "zero_reserve"
        else:
            if self.chunk_index is None:
                chunks = chunk_turns(old, self.config)
            else:
                ids = {t.turn_id for t in old}
                chunks = tuple(c for c in self.chunk_index.chunks if c.source.turn_id in ids)
            searchable = [(c, lexical_tokens(c.content)) for c in chunks]
            searchable = [(c, terms) for c, terms in searchable if terms]
            if searchable:
                # BM25+ has positive IDF for one-document/small corpora. Its delta
                # also scores nonmatches: explicitly require lexical intersection.
                ranker = BM25Plus(
                    [terms for _, terms in searchable],
                    k1=self.config.k1,
                    b=self.config.b,
                    delta=1.0,
                )
                scores = ranker.get_scores(query)
                ranked = [
                    (float(score), c)
                    for (c, terms), score in zip(searchable, scores, strict=True)
                    if set(query).intersection(terms) and score > self.config.minimum_score
                ]
                ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))
                if ranked:
                    reason = "evidence_over_budget"
                for _, chunk in ranked:
                    if any(overlaps(chunk, existing) for existing in selected):
                        continue
                    candidate = selected + (chunk,)
                    if fits_block(
                        planned,
                        evidence_block(candidate, self.counter),
                        planned.plan.retrieval_tokens,
                        self.counter,
                    ):
                        selected = candidate
                    if len(selected) >= self.config.top_k:
                        break
        if selected:
            reason = "evidence_retrieved"
        block = evidence_block(selected, self.counter)
        result = set_block(
            planned,
            block,
            LayerDiagnostic(
                "RETRIEVE",
                reason,
                tuple(dict.fromkeys(c.source.turn_id for c in selected)),
                output_text_tokens=block.text_tokens,
            ),
        )
        return replace(result, retrieved_chunks=selected)
