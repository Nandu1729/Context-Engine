# Preserved 0.9.2 baseline before D093 service repair

Copied from the pre-existing C10 build;no rebuild or modified historical freeze.

- Wheel: `context_engineering_core-0.9.2-py3-none-any.whl`
- Wheel SHA256: `0b4e0d7bf09814fbaa62f29d725740fcee367d24074cfa2b8002185edb024d67`
- Original freeze: `baseline-freeze.json`
- Freeze SHA256: `e398f37b9c776c9c70587c5808bd27084b63376955c2891281e9481c20ad8f1c`
- Package source SHA256: `298ca2e71c4a9ed652f72a70bb2edfe678194353863e381db3ef8f9a7bf3dfdc`

`tests/test_runtime_transition.py` imports this real wheel in an isolated child
process with networking denied,checks the original experiment manifests and
reproduces the original qualification preparation exactly. No real ledger,
credentials,provider calls or historical records are changed. Existing archived
environments remain intact. Never use this baseline to imply the0.9.3 repair was
included in old benchmark results.
