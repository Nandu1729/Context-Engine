"""Pure-Python uncased BERT WordPiece tokenizer (standard library only).

Matches Hugging Face `tokenizers` BertNormalizer(lowercase, clean text, CJK spacing,
accent stripping) + BertPreTokenizer + WordPiece for the bundled embedding model's
vocabulary. Verified token-for-token on the benchmark corpus; rare code points whose
Unicode tables differ between Python and the Rust library may differ in which
characters become [UNK] (unknown tokens are dropped before pooling anyway).
"""

import re
import unicodedata
from functools import lru_cache

# ASCII fast path: drop control characters, tabs/newlines become spaces; every
# printable non-alphanumeric ASCII character is BERT punctuation.
_ASCII_CLEAN = {cp: None for cp in (*range(0, 9), 11, 12, *range(14, 32), 127)} | {
    9: " ",
    10: " ",
    13: " ",
}
_ASCII_WORDS = re.compile(r"[a-z0-9]+|[!-/:-@\[-`{-~]")


def _is_control(ch: str) -> bool:
    return ch not in "\t\n\r" and unicodedata.category(ch).startswith("C")


def _is_whitespace(ch: str) -> bool:
    return ch in " \t\n\r" or unicodedata.category(ch) == "Zs"


def _is_punctuation(ch: str) -> bool:
    cp = ord(ch)
    if 33 <= cp <= 47 or 58 <= cp <= 64 or 91 <= cp <= 96 or 123 <= cp <= 126:
        return True
    return unicodedata.category(ch).startswith("P")


def _is_cjk(cp: int) -> bool:
    return (
        0x4E00 <= cp <= 0x9FFF
        or 0x3400 <= cp <= 0x4DBF
        or 0x20000 <= cp <= 0x2A6DF
        or 0x2A700 <= cp <= 0x2B73F
        or 0x2B740 <= cp <= 0x2B81F
        or 0x2B820 <= cp <= 0x2CEAF
        or 0xF900 <= cp <= 0xFAFF
        or 0x2F800 <= cp <= 0x2FA1F
    )


class WordPiece:
    def __init__(self, vocab: list[str], *, unk: str = "[UNK]", max_chars: int = 100):
        self.ids = {token: i for i, token in enumerate(vocab)}
        self.unk_id = self.ids[unk]
        self.max_chars = max_chars
        self._word = lru_cache(maxsize=65536)(self._word_ids)

    def normalize(self, text: str) -> str:
        out = []
        for ch in text:
            cp = ord(ch)
            if cp == 0 or cp == 0xFFFD or _is_control(ch):
                continue
            if _is_whitespace(ch):
                out.append(" ")
            elif _is_cjk(cp):
                out.append(f" {ch} ")
            else:
                out.append(ch)
        text = unicodedata.normalize("NFD", "".join(out))
        # Per-character lowercasing: str.lower() would apply Greek final-sigma rules.
        return "".join(c.lower() for c in text if unicodedata.category(c) != "Mn")

    def words(self, text: str):
        if text.isascii():
            yield from _ASCII_WORDS.findall(text.translate(_ASCII_CLEAN).lower())
            return
        for chunk in self.normalize(text).split():
            word = ""
            for ch in chunk:
                if _is_punctuation(ch):
                    if word:
                        yield word
                        word = ""
                    yield ch
                else:
                    word += ch
            if word:
                yield word

    def _word_ids(self, word: str) -> tuple[int, ...]:
        if len(word) > self.max_chars:
            return (self.unk_id,)
        pieces, start = [], 0
        while start < len(word):
            end, found = len(word), None
            while start < end:
                piece = word[start:end] if start == 0 else "##" + word[start:end]
                if piece in self.ids:
                    found = self.ids[piece]
                    break
                end -= 1
            if found is None:
                return (self.unk_id,)
            pieces.append(found)
            start = end
        return tuple(pieces)

    def encode(self, text: str) -> list[int]:
        ids: list[int] = []
        for word in self.words(text):
            ids.extend(self._word(word))
        return ids
