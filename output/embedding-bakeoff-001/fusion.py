"""Compare fusion rules of BM25 + embeddings on original and reworded questions."""
import json, sys
from pathlib import Path
import numpy as np
from rank_bm25 import BM25Plus
from context_engine.config import RetrievalConfig
from context_engine.evaluation.corpus import load_bundle
from context_engine.evaluation.strategies import load_paraphrases
from context_engine.layers.retrieve import chunk_turns, lexical_tokens

b = load_bundle(); facts = b.facts
history = b.job(facts[0]["question"]).arguments["history"]
chunks = chunk_turns(history, RetrievalConfig()); texts = [c.content for c in chunks]; turns = [c.source.turn_id for c in chunks]
para = load_paraphrases(b); gold = [f["source_turn_id"] for f in facts]
QS = {"original": [f["question"] for f in facts], "reworded": [para[f["fact_id"]] for f in facts]}
bm25 = BM25Plus([lexical_tokens(t) for t in texts], k1=1.5, b=0.75)
which = sys.argv[1]
if which.startswith("m2v:"):
    from model2vec import StaticModel
    m = StaticModel.from_pretrained(which[4:]); ed, eq = m.encode, m.encode
else:
    import os
    from fastembed import TextEmbedding
    m = TextEmbedding(which, cache_dir=os.environ["FASTEMBED_CACHE"])
    ed, eq = (lambda x: list(m.passage_embed(x))), (lambda x: list(m.query_embed(x)))
D = np.asarray(ed(texts), dtype=np.float32); D /= np.linalg.norm(D, axis=1, keepdims=True)

def order(s): return list(np.argsort(-s, kind="stable"))
def rrf(orders, weights, k=60):
    s = np.zeros(len(texts))
    for o, w in zip(orders, weights):
        for r, i in enumerate(o): s[i] += w / (k + r + 1)
    return order(s)
def union(a, bm, na, nb):
    out = []
    for i in a[:na] + bm[:nb] + a:
        if i not in out: out.append(i)
    return out
def mm(x): return (x - x.min()) / (x.max() - x.min() + 1e-12)
rules = {
    "semantic": lambda s, bs: order(s),
    "bm25": lambda s, bs: order(bs),
    "rrf_1:1": lambda s, bs: rrf([order(s), order(bs)], [1, 1]),
    "rrf_2:1": lambda s, bs: rrf([order(s), order(bs)], [2, 1]),
    "union_2+2": lambda s, bs: union(order(s), order(bs), 2, 2),
    "union_3+1": lambda s, bs: union(order(s), order(bs), 3, 1),
    "score_0.7": lambda s, bs: order(0.7 * mm(s) + 0.3 * mm(bs)),
    "score_0.5": lambda s, bs: order(0.5 * mm(s) + 0.5 * mm(bs)),
}
out = {}
for qs, qq in QS.items():
    Q = np.asarray(eq(qq), dtype=np.float32); Q /= np.linalg.norm(Q, axis=1, keepdims=True)
    for name, rule in rules.items():
        hits = rr = 0
        for q, qv, g in zip(qq, Q, gold):
            top = [turns[i] for i in rule(D @ qv, np.asarray(bm25.get_scores(lexical_tokens(q))))]
            hits += g in top[:4]; rr += next((1 / (r + 1) for r, t in enumerate(top) if t == g), 0)
        out.setdefault(name, {})[qs] = f"{hits}/31 mrr {rr/31:.2f}"
print(which)
for name, v in out.items(): print(f"  {name:<10} original {v['original']:<16} reworded {v['reworded']}")
