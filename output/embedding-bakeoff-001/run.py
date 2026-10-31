"""Embedding bake-off on the frozen corpus: source-turn recall@4, MRR, speed, size."""
import json, sys, time, os
from pathlib import Path
import numpy as np
from rank_bm25 import BM25Plus
from context_engine.config import RetrievalConfig
from context_engine.evaluation.corpus import load_bundle
from context_engine.evaluation.strategies import load_paraphrases
from context_engine.layers.retrieve import chunk_turns, lexical_tokens

b = load_bundle(); facts = b.facts
history = b.job(facts[0]["question"]).arguments["history"]
chunks = chunk_turns(history, RetrievalConfig())
texts = [c.content for c in chunks]; turns = [c.source.turn_id for c in chunks]
para = load_paraphrases(b)
QS = {"original": [f["question"] for f in facts], "reworded": [para[f["fact_id"]] for f in facts]}
gold = [f["source_turn_id"] for f in facts]
K = 4

def score(rankings):
    hits, rr = 0, 0.0
    for order, g in zip(rankings, gold):
        top = [turns[i] for i in order]
        hits += g in top[:K]
        rr += next((1 / (r + 1) for r, t in enumerate(top) if t == g), 0)
    return hits, round(rr / len(gold), 3)

bm25 = BM25Plus([lexical_tokens(t) for t in texts], k1=1.5, b=0.75)
def bm25_rank(q): return list(np.argsort(-bm25.get_scores(lexical_tokens(q)), kind="stable"))

def rrf(*orders, k=60):
    s = np.zeros(len(texts))
    for o in orders:
        for r, i in enumerate(o): s[i] += 1 / (k + r + 1)
    return list(np.argsort(-s, kind="stable"))

results = {"chunks": len(texts)}
results["bm25"] = {qs: score([bm25_rank(q) for q in qq]) for qs, qq in QS.items()}

def run(name, embed_docs, embed_queries, size_mb):
    t = time.perf_counter(); D = np.asarray(embed_docs(texts), dtype=np.float32); index_s = time.perf_counter() - t
    D /= np.linalg.norm(D, axis=1, keepdims=True) + 1e-12
    out = {"size_mb": size_mb, "index_ms_per_chunk": round(index_s * 1000 / len(texts), 2)}
    for qs, qq in QS.items():
        t = time.perf_counter(); Q = np.asarray(embed_queries(qq), dtype=np.float32); q_ms = (time.perf_counter() - t) * 1000 / len(qq)
        Q /= np.linalg.norm(Q, axis=1, keepdims=True) + 1e-12
        sem = [list(np.argsort(-(D @ q), kind="stable")) for q in Q]
        out[qs] = {"semantic": score(sem), "hybrid": score([rrf(s, bm25_rank(q)) for s, q in zip(sem, qq)]), "query_ms": round(q_ms, 2)}
    results[name] = out; print(name, json.dumps(out), flush=True)

def dir_mb(p): return round(sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file()) / 1e6)

which = sys.argv[1]
if which.startswith("m2v:"):
    from model2vec import StaticModel
    m = StaticModel.from_pretrained(which[4:])
    from huggingface_hub import snapshot_download
    run(which, m.encode, m.encode, dir_mb(snapshot_download(which[4:])))
else:
    from fastembed import TextEmbedding
    cache = Path(os.environ["FASTEMBED_CACHE"])
    m = TextEmbedding(which, cache_dir=str(cache))
    run(which, lambda x: list(m.passage_embed(x)), lambda x: list(m.query_embed(x)), dir_mb(cache))
if which.startswith("m2v:minishlab/potion-base-8M"):
    print("bm25", json.dumps(results["bm25"]), "chunks", len(texts))
