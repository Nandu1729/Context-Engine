"""Lenient grading v2 tolerates formatting only; strict v1 is unchanged."""

import pytest

from context_engine.evaluation.grading import GRADERS, answer_correct, answer_correct_lenient

ALIASES = ("cert-marigold",)


@pytest.mark.parametrize(
    "answer",
    [
        "cert-marigold",
        "cert‑marigold",
        "cert–marigold.",
        " CERT-MARIGOLD! ",
        '{"answer": "cert‑marigold."}',
    ],
)
def test_lenient_accepts_formatting_variants(answer):
    assert answer_correct_lenient(answer, ALIASES)


@pytest.mark.parametrize(
    "answer",
    [
        "The certificate was cert-marigold.",
        "cert-marigolds",
        "cert marigold",
        "UNKNOWN",
        '{"value": "cert-marigold"}',
        '{"answer": 3}',
        "{bad",
    ],
)
def test_lenient_still_requires_the_exact_value(answer):
    assert not answer_correct_lenient(answer, ALIASES)


def test_strict_v1_unchanged():
    assert answer_correct("cert-marigold", ALIASES)
    assert not answer_correct("cert‑marigold", ALIASES)  # U+2011 non-breaking hyphen.
    assert not answer_correct("PostgreSQL.", ("PostgreSQL",))
    assert answer_correct_lenient("PostgreSQL.", ("PostgreSQL",))
    assert list(GRADERS) == ["strict-v1", "lenient-v2"]
