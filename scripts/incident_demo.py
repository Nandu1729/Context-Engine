"""Generate an offline, escaped HTML context inspection; never call a model."""

import argparse
import html
import json
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from context_engine.config import Settings
from context_engine.errors import ContextEngineError
from context_engine.inspection import load_job

SAMPLE = Path(__file__).resolve().parents[1] / "examples/incident-demo.json"


@contextmanager
def offline_network():
    """Python socket guard, not an OS sandbox; tokenizer vocabulary must be cached."""
    with ExitStack() as stack:
        for target in ("create_connection", "getaddrinfo", "socket.connect", "socket.connect_ex"):
            stack.enter_context(
                patch("socket." + target, side_effect=RuntimeError("Network disabled"))
            )
        yield


def escaped(value):
    return html.escape(str(value), quote=True)


def pretty(value):
    return escaped(json.dumps(value, ensure_ascii=False, indent=2))


def render(job, result, *, show_content=False, sample=False, title="Incident context demo"):
    """Never emit custom source IDs, diagnostics or bodies without content opt-in."""
    diag = result.diagnostics
    metrics = (
        ("Source turns", len(job.arguments["history"])),
        ("Estimated input tokens", diag.estimate.estimated_tokens),
        ("Input allowance", diag.input_allowance),
        ("Remaining estimated tokens", diag.remaining_tokens),
    )
    cards = "".join(
        f"<div class='metric'><strong>{value}</strong>{label}</div>" for label, value in metrics
    )
    if show_content:
        history = "".join(
            f"<details><summary>{escaped(turn.turn_id)} · "
            f"{len(turn.messages)} message(s)</summary>"
            f"<pre>{pretty([m.to_wire() for m in turn.messages])}"
            "</pre></details>"
            for turn in job.arguments["history"]
        )
        messages = "".join(
            f"<details open><summary>{escaped(message['role'])}</summary>"
            f"<pre>{pretty(message)}</pre></details>"
            for message in result.messages
        )
        body = f"""<section><h2>Question</h2><p>{escaped(job.arguments["question"])}</p></section>
<div class="columns"><section><h2>1. Original history</h2>
<p>Unchanged input records. Expand a turn to inspect it.</p>{history}</section>
<section><h2>2. Assembled messages</h2><p>Exact message dictionaries prepared by the engine;
not sent to a model. WINDOW and RETRIEVED blocks are evidence data.</p>{messages}</section></div>
<section><h2>3. Assembly diagnostics</h2><p>Omitted WINDOW turns can still contribute retrieved
chunks. A source ID does not prove its entire text survived; inspect the assembled messages.</p>
<details><summary>Selection, sources, estimates and fingerprints</summary>
<pre>{pretty(diag.to_dict())}</pre></details></section>"""
    else:
        body = """<section><h2>Content hidden</h2><p>Question, history, messages, source IDs and
diagnostics are withheld. Add --show-content only if you intend to save that data in HTML.
</p></section>"""
    label = "SYNTHETIC SAMPLE" if sample else "LOCAL INPUT · PROVENANCE NOT VERIFIED"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{escaped(title)}</title><style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif;
color: #172b40; background: #edf2f7; }}
body {{ max-width: 1320px; margin: auto; padding: 28px; line-height: 1.55; }}
header {{ background: #102b46; color: white; padding: 30px; border-radius: 16px; }}
h1 {{ margin: 8px 0; font-size: 2.1rem; }} h2 {{ font-size: 1.15rem; }}
.label {{ color: #aee4ec; font-size: .8rem; letter-spacing: .12em; }}
.metrics {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 14px; margin: 20px 0; }}
.metric, section {{ background: white; border: 1px solid #d4e0e9;
border-radius: 12px; padding: 20px; }}
.metric strong {{ display: block; font-size: 1.8rem; color: #075b69; }}
.columns {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
details {{ border-top: 1px solid #d4e0e9; padding: 12px 0; }}
summary {{ cursor: pointer; font-weight: 600; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #f1f5f9;
padding: 14px; border-radius: 8px; font-size: .8rem; }}
.notice {{ border-left: 4px solid #a66a00; padding: 12px 18px;
background: #fff6dc; margin: 20px 0; }}
@media(max-width: 760px) {{ body {{ padding: 12px; }} .columns {{ grid-template-columns: 1fr; }}
.metrics {{ grid-template-columns: repeat(2,1fr); }} }}
</style></head><body><header><div class="label">{label} · TEST_ONLY</div>
<h1>{escaped(title)}</h1><p>See what the engine keeps before asking a model.</p></header>
<div class="notice">No model called. No answer generated. Answer quality NOT_EVALUATED.
Estimates are not an exact provider token guarantee. Evidence retention does not verify truth
or prove resistance to prompt injection.</div><div class="metrics">{cards}</div>{body}
<section><h2>Try another input</h2><p>Change the question or budget and rerun the generator to a new
output path. This is a static local report, not a chat application.</p><p>Dataset inputs
must be mapped to inspection schema version 1. Keep answer labels and ground truth
separate from history, system instructions and pins. This renderer downloads nothing.</p></section>
<footer><p>Engine {escaped(diag.package_version)} · Offline context inspection only.
Content-enabled HTML contains plaintext input data;
keep it private and do not commit real data.</p></footer>
</body></html>"""


def build_report(input_path=None, *, budget=None, question=None, show_content=False):
    with offline_network():
        job = load_job(Path(input_path) if input_path is not None else SAMPLE, Settings())
        if question is not None:
            job = replace(job, arguments={**job.arguments, "question": question})
        result = job.run(input_cap=budget)
        return render(
            job, result, show_content=show_content, sample=input_path is None and question is None
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, help="Local inspection-v1 JSON; default: synthetic sample"
    )
    parser.add_argument("--budget", type=int, help="Override estimated input allowance")
    parser.add_argument(
        "--question", help="Override the question; avoid sensitive shell-history text"
    )
    parser.add_argument(
        "--show-content", action="store_true", help="Save plaintext source and context"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="New HTML file; never overwritten"
    )
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("Output exists; choose a new path")
    try:
        document = build_report(
            args.input, budget=args.budget, question=args.question, show_content=args.show_content
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(document)
    except (ContextEngineError, OSError, RuntimeError):
        print("Demo failed. Check input, budget, cached tokenizer and a new writable output path.")
        return 1
    print("Created local HTML demo. No model called; answer quality not evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
