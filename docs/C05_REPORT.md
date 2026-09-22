# C05 checkpoint report

Date: 2026-09-08. Package: 0.5.0. Status: implementation READY for owner review; live provider unverified.

## What was done

- Implemented the Groq async adapter, validated generation settings, controlled errors, bounded retries, deadlines and cancellation handling.
- Added private local SQLite accounting with atomic quota reservations, observed-usage settlement and evidence-backed reconciliation of uncertain requests.
- Added opt-in, security/snapshot-scoped replay with corruption checks and zero new provider cost on reuse. Cached-input pricing and reasoning/output usage remain separate.
- Added offline `provider-demo` and explicitly authorized `provider-probe`; default output hides answer bodies. Preserved C04 artifacts and created a new 0.5.0 source freeze without changing benchmark targets.

## Verification

323 tests pass, including 90 new provider/CLI cases. Tests cover concurrency, 429, missing keys, transport failures, cancellation, malformed/partial responses, corrupted cache, cross-scope replay binding and failed settlement. Lint, formatting, locked dependency checks, package builds and clean installed-wheel checks pass.

The [saved demonstration](../output/c05-provider-demo.json) makes two simulated calls, replays an identical request without new cost, executes a changed question and blocks changed generation when quota is exhausted. Zero live inference calls and zero actual inference spend. The current offline benchmark still retrieves the flagship at 804/900 estimated tokens.

## Limits and next checkpoint

No live provider availability, token calibration, model accuracy or actual savings has been measured. Local reservation limits are not an absolute provider-billing guarantee. Replay retention/deletion, durable conversation memory, service authentication and operational qualification remain later gates. See [provider contracts](PROVIDER.md).

Next: C06 — connect the frozen benchmark to the adapter and produce reproducible V1 results/reports. Offline work can proceed when requested. Live completion requires credentials, explicit spending authorization/account limits and owner review of the still-pending evaluation targets. No checkpoint is marked owner-accepted automatically.
