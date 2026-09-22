"""Validated scalar configuration; no models, tokenizer, provider or benchmark imports."""

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigurationError

CONFIG_DIRECTORY = Path(__file__).resolve().parent
MAX_INSPECTION_BYTES = 2_000_000
MAX_INSPECTION_TURNS = 10_000


def nonnegative_integer(name: str, value: int, *, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ConfigurationError("Expected an integer within range", field=name, minimum=minimum)


@dataclass(frozen=True, slots=True)
class BudgetConfig:
    input_cap: int = 3000
    model_capacity: int = 131072
    completion_reservation: int = 256
    retrieval_reserve: int = 280
    summary_reserve: int = 80
    provider_input_cap: int | None = None

    def __post_init__(self) -> None:
        for name in ("input_cap", "model_capacity", "completion_reservation"):
            nonnegative_integer(name, getattr(self, name), minimum=1)
        for name in ("retrieval_reserve", "summary_reserve"):
            nonnegative_integer(name, getattr(self, name))
        if self.provider_input_cap is not None:
            nonnegative_integer("provider_input_cap", self.provider_input_cap, minimum=1)
        if self.completion_reservation >= self.model_capacity:
            raise ConfigurationError("Completion reservation leaves no input capacity")
        if self.retrieval_reserve + self.summary_reserve > self.input_allowance:
            raise ConfigurationError("Layer reserves exceed the input allowance")

    @property
    def input_allowance(self) -> int:
        ceilings = [self.input_cap, self.model_capacity - self.completion_reservation]
        if self.provider_input_cap is not None:
            ceilings.append(self.provider_input_cap)
        return min(ceilings)


@dataclass(frozen=True, slots=True)
class TokenizerConfig:
    encoding_name: str = "o200k_harmony"
    calibration_factor: float = 1.07
    adapter_overhead_tokens: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.encoding_name, str) or not self.encoding_name.strip():
            raise ConfigurationError("Tokenizer name must be non-empty", field="encoding_name")
        factor = self.calibration_factor
        if (
            type(factor) not in (int, float)
            or factor < 1
            or (isinstance(factor, float) and not math.isfinite(factor))
        ):
            raise ConfigurationError("Calibration factor must be finite and at least one")
        nonnegative_integer("adapter_overhead_tokens", self.adapter_overhead_tokens)


@dataclass(frozen=True, slots=True)
class CapConfig:
    max_tokens: int = 35
    head_tokens: int = 22
    tail_tokens: int = 8

    def __post_init__(self) -> None:
        for name in ("max_tokens", "head_tokens", "tail_tokens"):
            nonnegative_integer(name, getattr(self, name), minimum=1)
        if max(self.head_tokens, self.tail_tokens) > self.max_tokens:
            raise ConfigurationError("CAP head/tail limits exceed the message cap")


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    chunk_characters: int = 360
    overlap_characters: int = 80
    top_k: int = 4
    minimum_score: float = 0.0
    k1: float = 1.5
    b: float = 0.75

    def __post_init__(self) -> None:
        nonnegative_integer("chunk_characters", self.chunk_characters, minimum=1)
        nonnegative_integer("overlap_characters", self.overlap_characters)
        nonnegative_integer("top_k", self.top_k, minimum=1)
        if self.overlap_characters >= self.chunk_characters:
            raise ConfigurationError("Chunk overlap must be smaller than chunk size")
        for name in ("minimum_score", "k1", "b"):
            value = getattr(self, name)
            try:
                valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise ConfigurationError("Invalid retrieval parameter", field=name)
        if self.k1 <= 0 or self.b > 1:
            raise ConfigurationError("BM25 requires positive k1 and b between zero and one")


@dataclass(frozen=True, slots=True)
class Settings:
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    tokenizer: TokenizerConfig = field(default_factory=TokenizerConfig)
    output_dir: Path = CONFIG_DIRECTORY / "output"
    cap: CapConfig = field(default_factory=CapConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)

    def __post_init__(self) -> None:
        if not isinstance(self.budget, BudgetConfig) or not isinstance(
            self.tokenizer, TokenizerConfig
        ):
            raise ConfigurationError(
                "Settings require validated budget and tokenizer configuration"
            )
        if not isinstance(self.cap, CapConfig) or not isinstance(self.retrieval, RetrievalConfig):
            raise ConfigurationError("Settings require validated layer configuration")
        try:
            path = Path(self.output_dir).expanduser()
            if not path.is_absolute():
                path = CONFIG_DIRECTORY / path
            object.__setattr__(self, "output_dir", path.resolve())
        except (TypeError, ValueError, OSError, RuntimeError):
            raise ConfigurationError("Invalid output directory", field="output_dir") from None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ

        def integer(key: str, default: int) -> int:
            try:
                return int(env[key]) if key in env else default
            except (ValueError, TypeError):
                raise ConfigurationError(
                    "Environment setting must be an integer", field=key
                ) from None

        def number(key: str, default: float) -> float:
            try:
                return float(env[key]) if key in env else default
            except (TypeError, ValueError, OverflowError):
                raise ConfigurationError("Environment setting must be numeric", field=key) from None

        try:
            factor = float(env.get("TOKENIZER_FUDGE", "1.07"))
        except (ValueError, TypeError):
            raise ConfigurationError(
                "Environment setting must be numeric", field="TOKENIZER_FUDGE"
            ) from None
        return cls(
            budget=BudgetConfig(
                input_cap=integer("CONTEXT_BUDGET_TOKENS", 3000),
                model_capacity=integer("MODEL_CONTEXT_TOKENS", 131072),
                completion_reservation=integer("MAX_COMPLETION_TOKENS", 256),
                retrieval_reserve=integer("RETRIEVAL_RESERVE_TOKENS", 280),
                summary_reserve=integer("SUMMARY_RESERVE_TOKENS", 80),
                provider_input_cap=(
                    integer("PROVIDER_INPUT_CAP_TOKENS", 0)
                    if "PROVIDER_INPUT_CAP_TOKENS" in env
                    else None
                ),
            ),
            tokenizer=TokenizerConfig(
                encoding_name=env.get("TOKENIZER_NAME", "o200k_harmony"),
                calibration_factor=factor,
                adapter_overhead_tokens=integer("ADAPTER_OVERHEAD_TOKENS", 0),
            ),
            output_dir=Path(env.get("CONTEXT_OUTPUT_DIR", str(CONFIG_DIRECTORY / "output"))),
            cap=CapConfig(
                max_tokens=integer("CAP_MAX_TOKENS", 35),
                head_tokens=integer("CAP_HEAD_TOKENS", 22),
                tail_tokens=integer("CAP_TAIL_TOKENS", 8),
            ),
            retrieval=RetrievalConfig(
                chunk_characters=integer("RETRIEVAL_CHUNK_CHARACTERS", 360),
                overlap_characters=integer("RETRIEVAL_OVERLAP_CHARACTERS", 80),
                top_k=integer("RETRIEVAL_TOP_K", 4),
                minimum_score=number("RETRIEVAL_MINIMUM_SCORE", 0.0),
                k1=number("BM25_K1", 1.5),
                b=number("BM25_B", 0.75),
            ),
        )
