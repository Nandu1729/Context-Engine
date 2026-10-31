"""Fusion variants on: original, reworded, and needle-in-filler (memory demo) cases."""
import numpy as np
from rank_bm25 import BM25Plus
from context_engine.config import RetrievalConfig
from context_engine.embeddings import default_embedder
from context_engine.evaluation.corpus import load_bundle
from context_engine.evaluation.strategies import load_paraphrases
from context_engine.layers.retrieve import chunk_turns, lexical_tokens
from context_engine.models import Message, Role, Scope, Turn

e = default_embedder()
def corpus(turns):
    ch = chunk_turns(turns, RetrievalConfig()); return [c.content for c in ch], [c.source.turn_id for c in ch]
b = load_bundle(); h = b.job(b.facts[0]["question"]).arguments["history"]; para = load_paraphrases(b)
sets = {}
texts, turns = corpus(h)
sets["original"] = (texts, turns, [(f["question"], f["source_turn_id"]) for f in b.facts])
sets["reworded"] = (texts, turns, [(para[f["fact_id"]], f["source_turn_id"]) for f in b.facts])
# Needle-in-filler: each fact sentence buried in filler, questions reuse its words (memory demo shape).
s = Scope("d", "d"); needles = []
facts = b.facts
for k, f in enumerate(facts):
    sentence = next(x for x in [m.content for t in h for m in t.messages if m.message_id == f["source_message_id"]][0].split(". ") if f["expected"] in x)
    needles.append(Turn(f"n{k}", s, (Message(f"n{k}", Role.USER, "routine telemetry. " * 60 + sentence + ". " + "routine telemetry. " * 60),)))
fill = [Turn(f"f{k}", s, (Message(f"f{k}", Role.USER, f"Recent update {k}. " + "routine checks continue. " * 40),)) for k in range(60)]
nt, nturns = corpus(needles + fill)
sets["needle"] = (nt, nturns, [(f["question"], f"n{k}") for k, f in enumerate(facts)])
sets["needle-reworded"] = (nt, nturns, [(para[f["fact_id"]], f"n{k}") for k, f in enumerate(facts)])

def mm(x): return (x - x.min()) / (x.max() - x.min() + 1e-12)
def run(w, guard):
    out = []
    for name, (texts, turns, qa) in sets.items():
        D = np.asarray(e.embed_documents(texts)); toks = [lexical_tokens(t) for t in texts]
        bm = BM25Plus(toks, k1=1.5, b=0.75); hits = 0
        for q, gold in qa:
            qt = sorted(set(lexical_tokens(q))); bs = np.asarray(bm.get_scores(qt))
            s = w * mm(D @ np.asarray(e.embed_query(q))) + (1 - w) * mm(bs)
            order = list(np.argsort(-s, kind="stable"))
            if guard is not None:
                cover = np.array([len(set(qt) & set(t)) / len(qt) for t in toks])
                strong = [i for i in np.argsort(-bs, kind="stable")[:1] if cover[i] >= guard]
                order = strong + [i for i in order if i not in strong]
            hits += gold in [turns[i] for i in order[:4]]
        out.append(f"{name} {hits}/31")
    return " | ".join(out)
for w in (0.7, 0.5, 0.3):
    for guard in (None, 0.5, 0.6):
        print(f"w={w} guard={guard}: {run(w, guard)}")
print("keyword only:", run(0.0, None))
