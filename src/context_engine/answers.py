"""Opt-in exact JSON answer conformance; never truth grading or inference."""

import json
import re
import unicodedata
from dataclasses import dataclass

from .errors import ContractError

MAX_DOCUMENT_BYTES = 16384
PATTERNS = {
    "ascii_identifier": r"[A-Za-z0-9][A-Za-z0-9._:/-]*",
    "integer": r"(?:0|-?[1-9][0-9]*|UNKNOWN)",
}


@dataclass(frozen=True, slots=True)
class AnswerContract:
    """Strict value preservation. The caller owns evidence and authorization checks."""

    kind: str = "text"
    max_characters: int = 512

    def __post_init__(self):
        if self.kind not in ("text", "ascii_identifier", "integer"):
            raise ContractError("Unsupported answer kind")
        if type(self.max_characters) is not int or not 7 <= self.max_characters <= 2048:
            raise ContractError("Answer length limit must be between7 and2048")

    def json_schema(self) -> dict:
        value = {"type": "string", "minLength": 1, "maxLength": self.max_characters}
        if self.kind in PATTERNS:
            value["pattern"] = "^(?:" + PATTERNS[self.kind] + ")$"
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["answer"],
            "properties": {"answer": value},
        }

    def instructions(self) -> str:
        constraint = {
            "text": "Preserve the exact value, including case and Unicode characters.",
            "ascii_identifier": "Use an exact ASCII identifier; never replace its hyphens or case.",
            "integer": "Use a base-ten integer string without plus signs or leading zeros.",
        }[self.kind]
        return (
            'Return only one JSON object with exactly one string field named "answer". '
            'If evidence is missing or unresolved, return {"answer":"UNKNOWN"}. '
            "Do not include Markdown, explanations, extra fields, or surrounding value whitespace. "
            "The value must be a single line with no control characters. "
            f"Maximum value length: {self.max_characters} characters. " + constraint
        )

    def parse(self, document: str) -> str:
        """Reject, never repair/extract/normalize. Sanitized errors omit response bodies."""
        try:
            if not isinstance(document, str) or len(document) > MAX_DOCUMENT_BYTES:
                raise ValueError
            if len(document.encode("utf-8")) > MAX_DOCUMENT_BYTES:
                raise ValueError

            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError
                    result[key] = value
                return result

            def invalid_constant(_value):
                raise ValueError

            value = json.loads(document, object_pairs_hook=pairs, parse_constant=invalid_constant)
            if not isinstance(value, dict) or set(value) != {"answer"}:
                raise ValueError
            answer = value["answer"]
            if (
                not isinstance(answer, str)
                or not 1 <= len(answer) <= self.max_characters
                or answer != answer.strip()
                or any(unicodedata.category(c) in {"Cc", "Cs", "Zl", "Zp"} for c in answer)
            ):
                raise ValueError
            answer.encode("utf-8")
            if self.kind in PATTERNS and not re.fullmatch(PATTERNS[self.kind], answer):
                raise ValueError
            return answer
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ContractError("Answer does not conform to the exact JSON contract") from None
