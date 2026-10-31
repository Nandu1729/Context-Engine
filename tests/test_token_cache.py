"""The process-wide token-count cache returns identical counts and stays bounded."""

import tiktoken

from context_engine import tokens
from context_engine.config import TokenizerConfig
from context_engine.tokens import TiktokenCounter


def test_cached_counts_equal_direct_encoding():
    counter = TiktokenCounter()
    encoding = tiktoken.get_encoding("o200k_harmony")
    samples = [
        "",
        "hello",
        "<|endoftext|> stays ordinary",
        "x" * tokens.CACHE_MAX_TEXT,
        "é漢🙂 " * 50,
    ]
    for text in samples:
        assert counter.count_text(text) == len(encoding.encode_ordinary(text))
        assert counter.count_text(text) == counter.count_text(text)  # Second call hits the cache.


def test_long_texts_bypass_the_cache():
    counter = TiktokenCounter()
    tokens._cached_count.cache_clear()
    long_text = "word " * (tokens.CACHE_MAX_TEXT // 4)
    assert len(long_text) > tokens.CACHE_MAX_TEXT
    counter.count_text(long_text)
    assert tokens._cached_count.cache_info().currsize == 0
    counter.count_text("short")
    assert tokens._cached_count.cache_info().currsize == 1


def test_cache_is_bounded_and_keyed_by_encoding():
    assert tokens._cached_count.cache_info().maxsize == 32768
    a = TiktokenCounter(TokenizerConfig(encoding_name="o200k_harmony"))
    b = TiktokenCounter(TokenizerConfig(encoding_name="cl100k_base"))
    text = "Encodings differ on this sentence: ﻿naïve café."
    assert a.count_text(text) == len(tiktoken.get_encoding("o200k_harmony").encode_ordinary(text))
    assert b.count_text(text) == len(tiktoken.get_encoding("cl100k_base").encode_ordinary(text))
