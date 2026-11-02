"""Lenient grading v3 (D119): articles, punctuation, number words and a bare number for
"<number> <unit>". Strict v1 and lenient v2 are unchanged and stay the only GRADERS."""

import pytest

from context_engine.evaluation.grading import (
    GRADERS,
    answer_correct,
    answer_correct_lenient,
    answer_correct_lenient_v3,
    v3_tokens,
)


@pytest.mark.parametrize(
    "reply,gold",
    [
        ("The bike.", "bike"),  # Leading article and punctuation.
        ("bike", "The bike."),
        ("Mindful.org", "Mindful.org."),  # Punctuation stripped from BOTH sides.
        ("3 times a week", "Three times a week."),  # Number word = digit.
        ("21 days", "twenty-one days"),
        ("3", "3 days."),  # Number without its unit.
        ("3", "three days"),
        ("3.5", "3.5 weeks"),
        ("1300", "$1,300"),
        ("Trader Joes", "Trader Joe's"),
        (
            "University of California Los Angeles (UCLA)",
            "University of California, Los Angeles (UCLA)",
        ),
        ('{"answer": "the bike"}', "bike"),
    ],
)
def test_v3_accepts_same_meaning_in_another_format(reply, gold):
    assert answer_correct_lenient_v3(reply, (gold,))


@pytest.mark.parametrize(
    "reply,gold",
    [
        ("3 weeks", "3 days"),  # Different unit.
        ("4", "3 days"),  # Different number.
        ("3", "three times a week"),  # More than a unit is missing.
        ("3", "3 days and 2 hours"),
        ("3 days", "3"),  # Extra unit in the reply is not accepted.
        ("35", "3.5 weeks"),
        ("3", "3.5 weeks"),
        ("bikes", "bike"),
        ("It was the bike.", "bike"),  # Prose containing the answer.
        ("University of Melbourne", "University of Melbourne in Australia"),  # Partial.
        ("unknown", "bike"),
        ("", "bike"),
        ("The", "the"),  # Nothing left after the article.
        ('{"value": "bike"}', "bike"),
        ('{"answer": 3}', "3"),
        ("{bad", "bike"),
    ],
)
def test_v3_still_fails_different_or_partial_answers(reply, gold):
    assert not answer_correct_lenient_v3(reply, (gold,))


def test_v3_tokens():
    assert v3_tokens("An hour and a half") == ["hour", "and", "a", "half"]
    assert v3_tokens("ninety-nine") == ["99"] and v3_tokens("20 one") == ["20", "1"]
    assert v3_tokens("v2.0.1, 0.5 hours") == ["v2.0.1", "0.5", "hours"]


def test_v1_and_v2_unchanged():
    assert not answer_correct("The bike.", ("bike",))
    assert not answer_correct_lenient("The bike.", ("bike",))
    assert not answer_correct_lenient("Mindful.org", ("Mindful.org.",))
    assert list(GRADERS) == ["strict-v1", "lenient-v2"]
