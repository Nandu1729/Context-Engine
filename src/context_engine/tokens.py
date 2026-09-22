"""Full-request local estimates with replaceable serialization and explicit uncertainty."""

import hashlib
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol, runtime_checkable

from .config import TokenizerConfig
from .errors import ContractError, TokenizerUnavailable
from .models import ChatRequest, canonical_json, integer_value, text_value


@runtime_checkable
class RequestSerializer(Protocol):
    name: str

    def serialize(self, request: ChatRequest) -> str: ...


@dataclass(frozen=True, slots=True)
class CanonicalChatSerializer:
    """Counts all prompt-bearing JSON, NOT a provider's private chat template.

    Model IDs and sampling options are not prompt content. Tool schemas, names,
    call arguments, results, roles and message framing are included.
    """

    name: str = "canonical-chat-json-v1"

    def serialize(self, request: ChatRequest) -> str:
        return canonical_json(request.to_wire())


@dataclass(frozen=True, slots=True)
class TokenEstimate:
    serialized_tokens: int
    message_content_tokens: int
    tool_schema_tokens: int
    adapter_overhead_tokens: int
    calibration_factor: float
    tokenizer_name: str
    tokenizer_version: str
    serializer_name: str
    request_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "serialized_tokens",
            "message_content_tokens",
            "tool_schema_tokens",
            "adapter_overhead_tokens",
        ):
            integer_value(name, getattr(self, name))
        if (
            type(self.calibration_factor) not in (int, float)
            or self.calibration_factor < 1
            or (
                isinstance(self.calibration_factor, float)
                and not math.isfinite(self.calibration_factor)
            )
        ):
            raise ContractError("Invalid estimate calibration factor")
        for name in (
            "tokenizer_name",
            "tokenizer_version",
            "serializer_name",
            "request_fingerprint",
        ):
            text_value(name, getattr(self, name))

    @property
    def estimated_tokens(self) -> int:
        return math.ceil(
            (self.serialized_tokens + self.adapter_overhead_tokens)
            * Fraction(str(self.calibration_factor))
        )

    @property
    def serialization_delta_tokens(self) -> int:
        # This is signed: BPE counts across boundaries need not be additive.
        return self.serialized_tokens - self.message_content_tokens - self.tool_schema_tokens

    def to_dict(self) -> dict:
        return {
            "estimated_tokens": self.estimated_tokens,
            "serialized_tokens": self.serialized_tokens,
            "message_content_tokens": self.message_content_tokens,
            "tool_schema_tokens": self.tool_schema_tokens,
            "serialization_delta_tokens": self.serialization_delta_tokens,
            "adapter_overhead_tokens": self.adapter_overhead_tokens,
            "calibration_padding_tokens": (
                self.estimated_tokens - self.serialized_tokens - self.adapter_overhead_tokens
            ),
            "calibration_factor": self.calibration_factor,
            "tokenizer_name": self.tokenizer_name,
            "tokenizer_version": self.tokenizer_version,
            "serializer_name": self.serializer_name,
            "request_fingerprint": self.request_fingerprint,
            "provider_accounting_verified": False,
        }


@runtime_checkable
class TokenCounter(Protocol):
    def count_text(self, text: str) -> int: ...

    def count_request(self, request: ChatRequest) -> TokenEstimate: ...


class TiktokenCounter:
    def __init__(
        self, config: TokenizerConfig | None = None, serializer: RequestSerializer | None = None
    ) -> None:
        self.config = config if config is not None else TokenizerConfig()
        self.serializer = serializer if serializer is not None else CanonicalChatSerializer()
        text_value("serializer_name", self.serializer.name)
        try:
            import tiktoken

            self._encoding = tiktoken.get_encoding(self.config.encoding_name)
            self._version = tiktoken.__version__
        except Exception:
            # Includes unavailable encoding, missing install, download/hash/cache failures.
            # Never include raw transport errors or filesystem/provider details.
            raise TokenizerUnavailable(
                "Tokenizer unavailable; verify the encoding, installation "
                "and cached tokenizer assets"
            ) from None

    def count_text(self, text: str) -> int:
        text_value("text", text, nonempty=False)
        # Source text that resembles special control tokens remains ordinary data.
        return len(self._encoding.encode_ordinary(text))

    def count_request(self, request: ChatRequest) -> TokenEstimate:
        rendered = self.serializer.serialize(request)
        return TokenEstimate(
            serialized_tokens=self.count_text(rendered),
            message_content_tokens=sum(self.count_text(m.content) for m in request.messages),
            tool_schema_tokens=(
                self.count_text(canonical_json([t.to_wire() for t in request.tools]))
                if request.tools
                else 0
            ),
            adapter_overhead_tokens=self.config.adapter_overhead_tokens,
            calibration_factor=self.config.calibration_factor,
            tokenizer_name=self.config.encoding_name,
            tokenizer_version=self._version,
            serializer_name=self.serializer.name,
            request_fingerprint=hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        )
