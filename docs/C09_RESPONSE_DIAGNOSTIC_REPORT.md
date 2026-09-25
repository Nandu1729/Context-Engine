# C09 response-shape diagnostics — D082 complete

Recorded2026-09-24. **2/2 authorized calls completed;budget exhausted.** Original
Groq free-tier account,current.env,20b/256 output,no retries or prompt changes.

| Diagnostic | Raw content before parsing | Result |
|---|---|---|
|long-history/PRIMARY/900|Present string,0 characters|Empty answer reproduced|
|conflict/CONTROL/900|Present string,20 characters|Valid UNKNOWN JSON|

Both responses reported stop;neither included reasoning/refusal fields or tool
calls. The native parser preserved content exactly. This confirms an empty final
content field at the provider response boundary for the long-history diagnostic,
not local parser text loss. Provider/model internal cause is still unknown.
Output usage47 and65tokens is below256;increasing the cap is not justified by this
evidence. The second call succeeding does not repair its historical failed answer.

## Accounting and preservation

1,230input+112output=**1,342tokens**,configured$0,not independent billing verification.
All687 preceding ledger rows hash-identical. Account689attempts/1,105,138tokens,
zero unresolved holds. Neither diagnostic replaces a benchmark slot;live002 stays
PRIMARY14/16,overall25/32,strict target FAIL. No additional calls authorized.

[Diagnostic evidence](../output/c09-response-diagnostic-002/report.json) binds
sanitized response-shape metadata to claims and parsed-completion hashes. No raw
HTTP body,reasoning text,headers or keys retained. Socket-disabled replay is
byte-identical,SHA256`ae4ef86a391d2c3107d121533c0e8740f0330ee12e9b9c931629851e532d5468`.
ExecutionID`bfa02b1498b18862c9c56ef41caaca2d641d14d0d1dad4b8f27cde2005e4da43`.

## Verification

Nine targeted tests PASS in5.11s;lint/format pass. Tests cover metadata secrecy,
malformed shapes,exact two-slot selection,transparent native parsing,exclusive
evidence,full fake dispatch/accounting and zero calls on completed resume.

Initial zero-call diagnostic001 manifest was created during preflight;its report
reuse incorrectly assumed paired qualification cases. No real calls occurred.
Preserve that manifest and archived initial script;correct reporting under new
diagnostic002 identity. Guard rejects any old001 claim. The approved cap remains
two total calls,not two per identity. All nine tests passed before live dispatch.
Protocol file retains the001 proposal name;actual executed identity is002.

## Next action

Keep the opt-in caller guard so empty content is not used as a valid answer.
Evaluate provider response-format enforcement as a possible mitigation offline;
it is not yet a proven fix. Any changed provider parameters need a new version,
targeted tests and a separately approved small live validation. Do not enlarge
the output budget blindly or rerun the full matrix. C09 remains ACTIVE;no owner
acceptance,default-policy adoption or C10 start.
