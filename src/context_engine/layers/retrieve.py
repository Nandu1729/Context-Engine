"""BM25+ over originals; optional recovery of missing chunks in capped WINDOW turns."""

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
from ..work import Cancellation, raise_if_cancelled, validate_cancellation
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


def chunk_turns(
    turns: tuple[Turn, ...], config: RetrievalConfig, *, cancellation: Cancellation | None = None
) -> tuple[Chunk, ...]:
    validate_cancellation(cancellation)
    raise_if_cancelled(cancellation)
    chunks = []
    version = f"characters-v1:{config.chunk_characters}:{config.overlap_characters}"
    stride = config.chunk_characters - config.overlap_characters
    for turn in turns:
        raise_if_cancelled(cancellation)
        for message in turn.messages:
            raise_if_cancelled(cancellation)
            message_hash = message.content_hash
            for start in range(0, len(message.content), stride):
                raise_if_cancelled(cancellation)
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


def window_messages(context: ContextCarrier) -> dict[tuple[str, str], str]:
    """Actual working content, not full-original provenance ranges on WINDOW blocks."""
    return {
        (turn.turn_id, message.message_id): message.content
        for turn in context.working_turns
        if turn.turn_id in context.plan.window_turn_ids
        for message in turn.messages
    }


def represented_in_window(chunk: Chunk, visible: dict[tuple[str, str], str]) -> bool:
    text = visible.get((chunk.source.turn_id, chunk.source.message_id))
    return text is not None and chunk.content in text


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
        visible = window_messages(planned)
        old = tuple(
            t
            for t in planned.original_turns
            if t.turn_id not in planned.plan.window_turn_ids
            or (
                self.config.recover_capped_window
                and any(m.content != visible[(t.turn_id, m.message_id)] for m in t.messages)
            )
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
                # Preserve the exact 0.8.0 call form when no token is supplied.
                chunks = (
                    chunk_turns(old, self.config)
                    if context.cancellation is None
                    else chunk_turns(old, self.config, cancellation=context.cancellation)
                )
            else:
                ids = {t.turn_id for t in old}
                chunks = tuple(c for c in self.chunk_index.chunks if c.source.turn_id in ids)
            searchable = []
            for chunk in chunks:
                raise_if_cancelled(context.cancellation)
                if represented_in_window(chunk, visible):
                    continue
                terms = lexical_tokens(chunk.content)
                if terms:
                    searchable.append((chunk, terms))
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
                raise_if_cancelled(context.cancellation)
                ranked = [
                    (float(score), c)
                    for (c, terms), score in zip(searchable, scores, strict=True)
                    if set(query).intersection(terms) and score > self.config.minimum_score
                ]
                ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))
                raise_if_cancelled(context.cancellation)
                if ranked:
                    reason = "evidence_over_budget"
                for _, chunk in ranked:
                    raise_if_cancelled(context.cancellation)
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
