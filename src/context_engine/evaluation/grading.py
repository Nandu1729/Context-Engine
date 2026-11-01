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


# grading-v2 (0.15.0, T8): tolerant of formatting only. Strict v1 above stays frozen
# so historical results remain comparable; reports should show both.
_DASHES = dict.fromkeys(
    map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"), "-"
)


def answer_correct_lenient(answer: str, aliases: tuple[str, ...]) -> bool:
    """v1 rules after mapping Unicode dashes to "-" and dropping trailing ".!?".

    Still exact-value grading: prose that merely contains the answer is wrong.
    """
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
    value = re.sub(r"[.!?]+$", "", value.translate(_DASHES).strip()).rstrip()
    return normalize(value) in {normalize(a.translate(_DASHES)) for a in aliases}


GRADERS = {"strict-v1": answer_correct, "lenient-v2": answer_correct_lenient}


# grading-v3 (0.17.0, D119): also tolerant of articles, punctuation, number words and
# a bare number for "<number> <unit>". Kept out of GRADERS so v1/v2 reports reproduce.
_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
_NUMBER_WORDS = {w: i for i, w in enumerate(_ONES)} | {w: 20 + 10 * i for i, w in enumerate(_TENS)}
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def v3_tokens(text: str) -> list[str]:
    """Words after v3 normalization: every non-alphanumeric character becomes a space,
    number words 0-99 become digits and one leading article is dropped. "1,000" ->
    "1000"; "3.5" keeps its point; apostrophes are removed ("Joe's" -> "joes")."""
    value = normalize(text.translate(_DASHES))
    value = re.sub(r"(?<=\d),(?=\d{3}\b)", "", value)
    value = re.sub(r"['\u2019]", "", value)
    value = "".join(
        c if c.isalnum() or c in "\0 " else " " for c in re.sub(r"(?<=\d)\.(?=\d)", "\0", value)
    ).replace("\0", ".")
    words, tokens = value.split(), []
    for previous, word in zip([None, *words], words, strict=False):
        number = _NUMBER_WORDS.get(word)
        if number is not None and previous in _TENS and number < 10:
            tokens[-1] = str(int(tokens[-1]) + number)  # "twenty one" -> 21
        elif number is not None:
            tokens.append(str(number))
        else:
            tokens.append(word)
    if tokens and tokens[0] in ("the", "a", "an"):
        tokens = tokens[1:]
    return tokens


def answer_correct_lenient_v3(answer: str, aliases: tuple[str, ...]) -> bool:
    """v3 tokens must be equal, or the reply is exactly the number of a "<number> <unit>"
    alias ("3" for "3 days"). Prose that merely contains the answer is still wrong."""
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
    reply = v3_tokens(value)
    if not reply:
        return False
    for alias in aliases:
        gold = v3_tokens(alias)
        if reply == gold:
            return True
        if (
            len(gold) == 2
            and len(reply) == 1
            and reply[0] == gold[0]
            and _NUMBER.fullmatch(gold[0])
            and not _NUMBER.search(gold[1])
        ):
            return True
    return False


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
