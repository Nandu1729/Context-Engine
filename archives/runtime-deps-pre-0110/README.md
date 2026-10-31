# Pre-0.11.0 dependency wheels

0.11.0 upgraded certifi (2026.7.22 → 2026.10.23) and urllib3 (2.7.0 → 2.8.0) for
security advisories. Historical runtime identities record the old versions, so
archived-runtime replay tests prepend these exact wheels. Downloaded from PyPI on
2026-10-31; hashes match the pre-upgrade `uv.lock`.

- `certifi-2026.7.22-py3-none-any.whl`: `62f22742b58a1a33014a2b6b706588a8d7e2a88ae7bd1a6ebe8c992928483775`.
- `urllib3-2.7.0-py3-none-any.whl`: `9fb4c81ebbb1ce9531cce37674bbc6f1360472bc18ca9a553ede278ef7276897`.

Use only for offline historical replay; they contain known vulnerabilities.
