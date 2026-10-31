# C11 — local semantic retrieval preflight

2026-10-03. Design/preflight COMPLETE; implementation, installation and embedding
evaluation NOT STARTED. Core0.9.6 and the working application stay unchanged.
This is an engineering proposal,not a quality result or owner acceptance.

## Choice and verified requirements

Test `BAAI/bge-small-en-v1.5` locally alongside existing keyword retrieval.
The rationale is the observed wording mismatch in the
[multi-event diagnosis](C11_MULTIEVENT_DIAGNOSTIC_REPORT.md),not a claim that this
model is universally best. The [lexical-diversity candidate](C11_DIVERSITY_REPORT.md)
remains rejected;do not retune or overwrite that experiment.

The publisher identifies this model as English/MIT,384-dimensional,with a512-token
sequence limit. Use the retrieval query prefix
`Represent this sentence for searching relevant passages: `,no passage prefix,
first-token CLS pooling and L2 normalization. This is not a multilingual candidate.
See the [publisher model card](https://huggingface.co/BAAI/bge-small-en-v1.5).

Public repository metadata inspected anonymously on2026-10-03:

- Revision:`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`.
- `onnx/model.onnx`:133,093,490bytes;published LFS SHA256
  `828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35`.
- Supporting allowlist:`tokenizer.json`711,396bytes,`tokenizer_config.json`366,
  `special_tokens_map.json`125,`config.json`743,`vocab.txt`231,508,
  `README.md`94,783. Together with weights,approximately134.2MB decimal.
- Source:[pinned files](https://huggingface.co/BAAI/bge-small-en-v1.5/tree/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a).
  Weights were NOT downloaded or locally hashed. Small-file Git blob identities
  are not SHA256 digests;calculate and freeze actual SHA256 values during setup.

Local read-only checks:Darwin arm64,Python3.12.13,42.7GiB free at inspection.
ONNX Runtime,tokenizers,Transformers,PyTorch and sentence-transformers are absent.
Use a separate experiment environment;do not edit root dependencies,root lockfile
or the working `.venv`. Proposed minimal runtime:CPU ONNX Runtime,tokenizers,NumPy
and their resolved dependencies. No vector database or PyTorch stack is needed by
this proposed implementation. Compatibility remains to be tested.

Observed PyPI candidates:onnxruntime1.30.0 has a CPython3.12/macOS14+arm64 wheel
(21,544,867bytes);tokenizers0.23.2 has a macOS11+arm64 abi3 wheel(3,101,593bytes).
These are availability observations,not a tested lock. Resolve and hash all
transitive packages in the isolated environment before any data run.
Sources:[ONNX Runtime package metadata](https://pypi.org/pypi/onnxruntime/1.30.0/json),
[tokenizers package metadata](https://pypi.org/pypi/tokenizers/0.23.2/json),
[official CPU setup](https://onnxruntime.ai/docs/get-started/with-python.html).

## Fixed first-candidate contract

These are proposed engineering settings,not measured improvements. Freeze the
implementation,environment,artifact manifest and protocol before observing results.

1. Load only verified local artifacts using explicit `CPUExecutionProvider`.
   Inspect ONNX inputs/outputs;reject unexpected dimensions/types or external files.
   No remote Python code,pickle loader,custom operators or automatic model fallback.
2. Preserve original source chunks,offsets,tenant/session boundaries and WINDOW
   eligibility. Dense retrieval must not require lexical overlap with the question.
   Reference answers/annotations never enter embeddings,ranking or assembly.
3. Disable encoder truncation. Reject a condition if any encoded query/passage
   exceeds512tokens including special tokens/prefix;do not silently discard text.
   Reject nonfinite/zero vectors;require384dimensions and deterministic tie-breaking.
4. Rank eligible chunks by normalized dot product and separately by unchanged BM25.
   Fuse each list's first50entries with equal contributions `1/(60 + rank)`,rank
   starting at1;absent entries contribute0. Break ties by chunk ID. No score tuning,
   redundancy penalty,reranker,threshold sweep or unregistered fallback.
5. Preserve existing source validation,overlap checks,top-k4,retrieval reserve280,
   summary reserve0,recovery OFF,and complete-request budgets900/3000. Greedily
   select from the fused order using existing admission rules. System,question and
   WINDOW must remain identical to baseline. A high similarity is not answerability.
6. Start with ephemeral,in-process embeddings only. No persistent vector cache or
   service integration. Any reuse is scoped by tenant/session/source revision and
   hash,chunk offsets,model/tokenizer identity and encoding configuration.

## Privacy and bounded execution

Separate public package/model downloads from data execution. Never read `.env`,
inherit API credentials or use a hosted embedding endpoint. Download allowlisted
files at the pinned revision into a new isolated location;verify before loading.
Record full resolved installation size;stop if downloads would exceed500MB.
Keep at least2GiB free. No silently substituted artifact/version.

During evaluation,load local files only,disable Hub telemetry/network features,
and deny Python sockets as in existing offline probes. This is a test guard,not
an OS-level network sandbox or a security audit of native libraries. Record that
limitation;do not promise network isolation stronger than actually verified.

Initial resource settings:one worker,two ORT intra-op threads,one inter-op thread,
batch16,at most10,000 eligible chunks per condition. Synthetic run wall-clock cap
10minutes enforced by parent process;timeout/error is an incomplete result,not a
skip/pass or permission to retry. Measure elapsed time and available memory before
choosing a separately frozen broader-run cap. No persistent prompt/vector export;
reports contain IDs,hashes,coverage,timing and token counts only.

## Required order and acceptance gates

1. Owner confirms isolated setup/download;then implement/test the loader,ranking,
   bounds,scope isolation and redacted failure paths with synthetic/fake encoders.
2. Download/verify the pinned model;validate real tokenizer/ONNX compatibility and
   repeatability on synthetic text. Freeze the complete execution identity.
3. Run the existing four synthetic cases at both budgets,unchanged. Require exact
   baseline reproduction,all conditions fitting,single fact1/1,direct events3/3,
   and paraphrase3/3 at both budgets. Missing-evidence case stays NOT_APPLICABLE,
   not a correct-abstention claim. Report every displaced original interval.
4. Only after that gate,freeze a separate development protocol and run existing
   35development rows,date-aware OFF,at900/3000. Reuse converted inputs read-only;
   do not reopen/rewrite the downloaded corpus or touch70held-out rows.
5. Require no loss of previously covered marked evidence intervals in any condition,
   no case-level complete-message regression,and improvement on at least one known
   failing multi-event case. Report partial and unmarked span losses separately;
   aggregate gains cannot hide regressions. Any failed prerequisite rejects adoption.
6. Even passing these gates only supports further research. English-only development
   retention does not establish answer accuracy,cost savings,multilingual behavior,
   independent qualification or safe production adoption. Further generation needs
   a new explicit bounded approval;all earlier provider budgets remain exhausted.

No action is required on the owner's dataset or API keys. Next action is isolated
setup approval,not another download of LongMemEval or another manual grading task.
