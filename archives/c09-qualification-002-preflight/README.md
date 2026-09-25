# Qualification002 preflight correction

The initial offline preparation failed before producing a report: the evaluator
attempted to decode an empty optional retrieved block as JSON. Initial focused
result:7 passed,19 setup errors. These are test harness errors,not provider failures.
The initial script and manifest are preserved here with their exact hashes.
The case bytes and [protocol](../../docs/C09_QUALIFICATION_PROTOCOL.md) did not change.

The corrected external harness skips empty blocks as absent evidence and uses the
new experiment identity `c09-qualification-002-r1`. Its manifest is under
`experiments/c09-qualification-002/manifest.json`;the directory remains a container
for this candidate family,not its immutable identity. Regression test explicitly
covers empty blocks. No engine tuning,case edits,threshold changes or live calls
occurred between identities. No qualification result was produced under002.

Do not execute the archived script:its workspace-relative resource paths belong
to the project script,not this audit-copy directory.
