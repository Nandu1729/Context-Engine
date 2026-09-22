"""Independent deterministic evidence/answer grading; no model judge or substring guesses."""

import json
import math
import re
import unicodedata

from ..errors import BenchmarkError


def normalize(text: str) -> str:
    if not isinstance(text, str):
        raise BenchmarkError("Grading requires text")
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Cf").split())


def present(text: str, aliases: tuple[str, ...]) -> bool:
    """Identifier boundaries: shard-1 is not shard-19, nor is 7 part of t7."""
    value = normalize(text)
    return any(
        re.search(r"(?<![\w.-])" + re.escape(normalize(alias)) + r"(?!\w|[-.]\w)", value)
        is not None
        for alias in aliases
    )


def answer_correct(answer: str, aliases: tuple[str, ...]) -> bool:
    """Exact alias or one-field JSON answer; prose containing the answer is not enough."""
    value = answer.strip()
    if value.startswith("{"):
        try:
            pairs = json.loads(value, object_pairs_hook=lambda items: items)
        except (ValueError, RecursionError):
            return False
        if not isinstance(pairs, list) or len(pairs) != 1 or pairs[0][0] != "answer":
            return False
        value = pairs[0][1]
        if not isinstance(value, str):
            return False
    return normalize(value) in {normalize(a) for a in aliases}


def proportion(successes: int, denominator: int) -> dict:
    if (
        type(successes) is not int
        or type(denominator) is not int
        or not 0 <= successes <= denominator
    ):
        raise BenchmarkError("Invalid metric denominator")
    if denominator == 0:
        return {"count": successes, "denominator": 0, "rate": None, "wilson95": None}
    p, z = successes / denominator, 1.959963984540054
    divisor = 1 + z * z / denominator
    center = (p + z * z / (2 * denominator)) / divisor
    radius = z * math.sqrt((p * (1 - p) + z * z / (4 * denominator)) / denominator) / divisor
    return {
        "count": successes,
        "denominator": denominator,
        "rate": p,
        "wilson95": [max(0.0, center - radius), min(1.0, center + radius)],
    }
