# Local demo/SDK milestone — ready to try

2026-10-02,D104. Owner said “ok continue” after the local-demo-first recommendation.
This selects the immediate delivery scope,not checkpoint or enterprise acceptance.

## Delivered

- One beginner entry command: `uv run --locked --offline python -m scripts.local_demo`.
  It calls the real public `assemble_context` SDK on the existing synthetic incident
  fixture,then runs the established memory lifecycle demo on temporary stores.
- [Plain-language walkthrough](LOCAL_QUICKSTART.md):open the sample,understand the
  original conversation,find rollback evidence,run checks and handle setup errors.
  No grading of unfamiliar LongMemEval conversations is needed to try this milestone.
- Fresh prepared HTML: `output/local-demo-001/index.html`;metadata-only verification
  report: `output/local-demo-001/report.json`. Existing historical demo files retained.
- README now distinguishes the working local demo,implemented memory/API and finished
  historical C06 benchmark from remaining production qualification. Removed stale
  “C06 incomplete” and “memory is future work” language.

## Verification

CLI executed successfully with15checks:6SDK checks and9memory lifecycle checks.
Twelve sample turns assemble to838/900 estimated input tokens. SampleCAP80 is
explicit,not the product default35. Required policy/question and source originals
preserved;deployment retrieved and rollback version present. Memory checks include
restart,index resumption/reuse,pin revision,deletion-safe restore and stale-cache
invalidation. Temporary synthetic databases are cleaned up on completion.

51focused tests PASS1.73s across8new launcher checks,existing HTML demo and strict
inspection tests. Launcher checks actual SDK/lifecycle behavior,metadata-only
reporting,no answer-quality claim,plain-language output,redacted errors,optional
output,existing-file/racing-writer protection and failing lifecycle propagation.
No full-suite or new remote platform run;September28CI does not cover this launcher.

Final8project-memory tests PASS0.87s;59focused tests total. Ruff lint/format,
source/link/index and whitespace checks PASS;hot memory894/900words.

The new HTML reproduces exactly from the unchanged renderer with Python networking
disabled. The older002HTML has historical footer wording and was not overwritten.
No visual layout change was made. Core0.9.6 SHA remains
`304253f7109add9df916592881d2ff4929da28bb13fea51fe020d1262e8196f2`.

Artifact SHA256:

- Launcher: `5cae7e0001346d2746b8607887957845019dcad5f769bb5c039246694f0f3345`.
- Report: `c8311fe826cf0950fde5709b758327ec5725366c4c7a13837f3dd3da5ba153ac`.
- HTML: `72f25c70100970326bf3743d930be8af30240bf24aa605bb1c892c43a13ec7d8`.

## Boundaries and handoff

No model call,credential read,provider-ledger access,original dataset access,
held-out run,core/default change,service launch or deployment. The overlap-union
prototype remains outside this demo. This is context preparation and memory
behavior—not an answer-generating chatbot,installed-wheel requalification or
enterprise readiness. Repository scripts require the checkout and existing cached
dependencies;first-time setup is documented separately.

The local milestone is READY to try;C09–C12 remain open as recorded in the
[completion audit](PROJECT_COMPLETION_STATUS.md).

## Local continuation: copyable SDK example

2026-10-02:owner says go to the next step after the synthetic HTML walkthrough.
Added `examples/sdk_quickstart.py`,using only the public installed SDK and standard
library. Three short synthetic turns,an explicit900token budget,default CAP/retrieval
and no summary reserve. `prepare_context()` returns the real `AssembledContext`;
no new production API or model adapter introduced.

`--question` changes the final question;`--show-context` explicitly displays prepared
messages. Default console output contains no conversation text. No output files or
database writes,credential reads,model calls,corpus/ledger access or core edits.
Public tokenizer assets must be cached;uv's offline flag is not a Python sandbox.

Seven new tests cover real evidence retention,required policy/question,repeatability,
fresh wire dictionaries,content opt-in,redacted errors,mandatory overflow and a
standalone isolated subprocess outside the checkout. Python sockets are denied
during tests after tokenizer initialization. Alongside8launcher tests:15PASS0.46s.
The custom root-cause command ran successfully at173/900estimated tokens,showing
the unchanged synthetic history and new final question,not a model answer.
Default command also ran successfully at183/900estimated tokens. Final8brain tests
PASS0.89s;23focused tests total. Ruff lint/format,whitespace and source/link/index
checks PASS;hot memory895/900words. No full suite was rerun.

Next owner task:copy the command in step4 of the [quickstart](LOCAL_QUICKSTART.md).
No dataset rating is required. A subsequent step can use the existing authenticated
local service demo;it was not launched here. No full-suite/CI/wheel qualification,
release approval or semantic-quality claim follows from this example.

## Application connection completed

Owner supplied successful183/900 and173/900SDK outputs plus API demo PASS for all
five checks,zero inference/external calls and stopped temporary server. These are
owner-reported results,not a fresh remote/platform qualification.

On request to complete the connection quickly,added `sample_app.py`:interactive
question or `--question`,optional `--show-context`,real SDK result,no persistence
or model call. Reuses the existing synthetic-history example;requires this checkout.
Blank input,cancellation and engine errors handled without echoing exception bodies;
prepared content is printed only with the explicit flag.

Six app tests plus7SDK tests PASS0.40s with Python sockets disabled after public
tokenizer initialization. Covers interactive and noninteractive entry,content opt-in,
no local output files,blank input,EOF/Ctrl+C and redacted errors. Actual command
`uv run --locked --offline python sample_app.py --question "Which version did we roll back to?" --show-context`
succeeded at174/900estimated tokens with rollback evidence preserved.

No core/default/credential/corpus/ledger edits,new provider requests,persistent API
server or deployment. Repeated owner walkthroughs are optional. Next bounded work
can connect an already-converted LongMemEval development input;the current app still
uses synthetic history only. Enterprise gates remain unchanged.
Final8brain tests PASS0.85s;21focused tests total. Source/link/index and whitespace
checks PASS;hot memory897/900words. No full-suite or remote CI rerun.

## Existing dataset connection completed — 2026-10-03

Owner approved connecting an already-prepared LongMemEval development example.
`sample_app.py --longmemeval` now uses existing row49baseline inspection input;
`--input` supports an explicitly selected converted input. Synthetic mode remains
available. Dataset mode takes its saved question/configuration without prompting;
conflicting source/question options reject before reading. No reference-answer
file is opened. Unknown ground-truth fields,raw corpus arrays and label objects
are rejected by the existing bounded strict inspection loader.

Actual integration:512source turns,892/900estimated input tokens,recovery OFF,
unchanged baseline mapping. Row49 confirmed in the saved development partition.
Prepared wire request and estimated tokens reproduce the saved baseline900export
exactly with Python sockets disabled. This is data integration,not a model answer,
official benchmark evaluation,full-evidence-retention claim or new date-mapping choice.

Twelve new regressions plus6existing app,7SDK and33inspection tests:58PASS1.50s.
Coverage includes saved question/configuration,content opt-in,file preservation,
only-input reads,label rejection,missing/malformed input,source conflicts and the
app's own socket guard. Test fixtures are synthetic;CI needs no downloaded dataset.
Scoped Ruff lint/format PASS. No full suite or remote CI rerun.

Original download SHA256 still
`d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`.
Selected input SHA256 before/after remains
`4798dc0fdb5174fb68efee364142c853fdb7ebcb207911e7bb74a9548f567fb5`.
No input/label export,original corpus,core/default,historical runner,provider ledger
or credential changes. No downloads,model calls,service launch or held-out execution.
The input remains in its existing Git-ignored private location;nothing is copied
into public examples. App output is status-only unless content display is requested.

[Quickstart step5](LOCAL_QUICKSTART.md) is the final handoff. No additional download
or manual connection task remains on this machine. Future answer generation needs
separate bounded authorization;all previous inference budgets remain exhausted.
Final8brain tests PASS0.89s;66focused tests total. Source/link/index and whitespace
checks PASS;hot memory895/900words.
