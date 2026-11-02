# Pre-1.0-defaults runtime (0.17.3)

The 0.17.3 wheel (as released on PyPI) and development freeze preserved before 0.18.0
gave `assemble_context` ChatMemory's retrieval defaults: a reserve of 40% of the input
allowance, one evidence chunk per 90 reserve tokens (at least 4) and at most one chunk
per turn (D124). Built from commit `0043859`.

- Wheel SHA256: `e4e36975f30709aed3ffae115fc0a16faab7a2b5485c2414486f3234c803b8cc`.
- Source hash: `134bf0f442387c6bed803580a668b5de566dde76b244aeb3483ccfdb0c590ca6`.
