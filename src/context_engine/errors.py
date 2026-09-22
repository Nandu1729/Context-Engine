"""Structured, content-free errors safe for default diagnostic output."""

from types import MappingProxyType
from typing import ClassVar


class ContextEngineError(Exception):
    code: ClassVar[str] = "context_engine_error"

    def __init__(self, message: str, **details: int | str) -> None:
        super().__init__(message)
        self.details = MappingProxyType(dict(details))

    def to_dict(self) -> dict:
        return {"code": self.code, "message": str(self), "details": dict(self.details)}


class ConfigurationError(ContextEngineError):
    code = "invalid_configuration"


class ContractError(ContextEngineError):
    code = "invalid_contract"


class TokenizerUnavailable(ContextEngineError):
    code = "tokenizer_unavailable"


class RequiredContextTooLarge(ContextEngineError):
    code = "required_context_too_large"


class LayerAllocationError(ContextEngineError):
    code = "layer_allocation_exceeds_budget"


class PromptTooLarge(ContextEngineError):
    code = "prompt_too_large"


class LayerStateError(ContextEngineError):
    code = "invalid_layer_state"


class CapBudgetError(ContextEngineError):
    code = "cap_budget_too_small"


class SummaryLeakageError(ContextEngineError):
    code = "summary_leakage"


class InspectionError(ContextEngineError):
    code = "invalid_inspection_input"


class SummaryPolicyError(ContextEngineError):
    code = "summary_policy_error"


class BenchmarkError(ContextEngineError):
    code = "invalid_benchmark"


class ProviderError(ContextEngineError):
    code = "provider_error"


class StorageError(ContextEngineError):
    code = "runtime_storage_error"


class QuotaError(ContextEngineError):
    code = "quota_exhausted"


class CacheError(ContextEngineError):
    code = "invalid_replay_cache"


class MemoryConflict(ContextEngineError):
    code = "memory_revision_conflict"


class MemoryIntegrityError(ContextEngineError):
    code = "memory_integrity_error"
