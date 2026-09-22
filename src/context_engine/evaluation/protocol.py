"""Versioned protocol, code/resource freeze and deterministic planned probe identities."""

import hashlib
import platform
from dataclasses import dataclass
from importlib import metadata, resources
from pathlib import Path

from .. import __version__
from ..config import BudgetConfig, CapConfig, RetrievalConfig, TokenizerConfig
from ..errors import BenchmarkError, ContextEngineError
from ..models import canonical_json
from ..pipeline import AssemblyOptions
from .corpus import Bundle, check_fixture, check_leakage, digest, read_resource, strict_json

VARIANTS = (
    ("A0", False, False, False, False, False),
    ("A1", False, False, False, False, True),
    ("A2", True, False, False, False, True),
    ("A3", True, True, False, False, True),
    ("A4", True, True, True, False, True),
    ("A5", True, True, True, True, True),
)
DEPENDENCIES = (
    "tiktoken",
    "rank-bm25",
    "numpy",
    "regex",
    "requests",
    "certifi",
    "charset-normalizer",
    "idna",
    "urllib3",
)


def code_hash() -> str:
    root = resources.files("context_engine")
    entries = []

    def visit(directory, prefix=""):
        for item in sorted(directory.iterdir(), key=lambda p: p.name):
            name = prefix + item.name
            if item.is_dir() and item.name != "__pycache__":
                visit(item, name + "/")
            elif item.name.endswith(".py"):
                entries.append((name, hashlib.sha256(item.read_bytes()).hexdigest()))

    visit(root)
    return digest(entries)


def runtime_identity() -> dict:
    return {
        "package_version": __version__,
        "python": platform.python_version(),
        "dependencies": {name: metadata.version(name) for name in DEPENDENCIES},
        "code_hash": code_hash(),
    }


def freeze_record(bundle: Bundle) -> dict:
    """Authoring helper, never called implicitly to bless drift during validation."""
    return {"schema_version": 1, "fixture_hashes": bundle.hashes, "runtime": runtime_identity()}


def load_freeze(directory: Path | None = None) -> dict:
    return strict_json(read_resource("freeze.json", directory))


def check_protocol(bundle: Bundle) -> None:
    try:
        p = bundle.get("protocol")
        expected = [
            dict(zip(("id", "cap", "pins", "retrieve", "summarize", "window"), row, strict=True))
            for row in VARIANTS
        ]
        if canonical_json(p["variants"]) != canonical_json(expected):
            raise BenchmarkError("The six declared variants changed")
        if p["approval"] not in ("owner_pending", "owner_approved"):
            raise BenchmarkError("Unknown protocol approval state")
        if (
            p["grading"]
            != {
                "normalization": "nfkc-casefold-whitespace-v1",
                "answer_mode": "exact-alias-or-json-answer",
                "presence_mode": "identifier-boundary-v1",
                "abstentions": ["UNKNOWN"],
            }
            or p["bm25_variant"] != "BM25Plus-delta1"
            or p["corpus_limits"] != {"turns": 100, "facts": 31}
        ):
            raise BenchmarkError("Declared grading or corpus policy differs from implementation")
        if p["summary_coverage"] != "frozen-content-bound-to-omitted-history":
            raise BenchmarkError("Unsupported summary coverage policy")
        if p["budgets"] != [900, 3000] or p["zone_boundaries"] != [33, 66, 100]:
            raise BenchmarkError("Unsupported version-1 evaluation protocol")
        if len(set(p["models"])) != len(p["models"]) or not p["models"]:
            raise BenchmarkError("Invalid model plan")
        if any(not isinstance(m, str) or not m.strip() for m in p["models"]):
            raise BenchmarkError("Invalid model identity")
        if p["generation"] != {
            "temperature": 0,
            "reasoning_effort": "low",
            "max_completion_tokens": 256,
        }:
            raise BenchmarkError("Unsupported version-1 generation settings")
        if p["targets"] != {
            "input_budget": 900,
            "variant": "A5",
            "fit": 31,
            "retained": 28,
            "correct": 27,
            "median_input_reduction": 0.9,
            "max_truncated": 0,
        }:
            raise BenchmarkError("Version-1 pre-registered targets changed")
        for cap in p["budgets"]:
            BudgetConfig(
                input_cap=cap,
                completion_reservation=p["generation"]["max_completion_tokens"],
                **p["budget"],
            )
        CapConfig(**p["cap"])
        RetrievalConfig(**p["retrieval"])
        TokenizerConfig(**p["tokenizer"])
    except BenchmarkError:
        raise
    except (KeyError, TypeError, ValueError, ContextEngineError):
        raise BenchmarkError("Malformed evaluation protocol") from None


@dataclass(frozen=True)
class Gate:
    gate: str
    status: str
    reason: str


def preflight(bundle: Bundle, frozen: dict) -> tuple[Gate, ...]:
    gates = []
    for identifier, operation in (("V1", check_fixture), ("V2", check_leakage)):
        try:
            operation(bundle)
            gates.append(Gate(identifier, "PASS", "checked"))
        except (ContextEngineError, KeyError, TypeError, ValueError, StopIteration):
            gates.append(
                Gate(
                    identifier,
                    "FAIL",
                    "fixture_integrity" if identifier == "V1" else "answer_leakage",
                )
            )
    try:
        check_protocol(bundle)
        if frozen != freeze_record(bundle):
            raise BenchmarkError("Frozen resources or execution identity changed")
        gates.append(Gate("V5", "PASS", "frozen_identity_matches"))
    except (ContextEngineError, KeyError, TypeError, ValueError):
        gates.append(Gate("V5", "FAIL", "configuration_or_code_drift"))
    return tuple(gates)


def require_preflight(bundle: Bundle, frozen: dict) -> None:
    failed = [g.gate for g in preflight(bundle, frozen) if g.status == "FAIL"]
    if failed:
        raise BenchmarkError("Benchmark preflight INVALID", gates=",".join(failed))


@dataclass(frozen=True)
class Manifest:
    payload_json: str

    def __post_init__(self):
        payload = strict_json(self.payload_json)
        object.__setattr__(self, "payload_json", canonical_json(payload))

    @property
    def data(self):
        return strict_json(self.payload_json)

    @property
    def run_id(self):
        return digest(self.data)

    @property
    def slots(self) -> tuple[dict, ...]:
        data = self.data
        return tuple(
            {
                "probe_id": digest([self.run_id, model, budget, variant, fact]),
                "model": model,
                "budget": budget,
                "variant": variant,
                "fact_id": fact,
            }
            for model in data["models"]
            for budget in data["budgets"]
            for variant in data["variants"]
            for fact in data["facts"]
        )

    def slot(self, identifier: str) -> dict:
        for slot in self.slots:
            if slot["probe_id"] == identifier:
                return slot
        raise BenchmarkError("Unknown planned probe ID")


def make_manifest(
    bundle: Bundle, frozen: dict, *, facts=None, models=None, budgets=None, variants=None
) -> Manifest:
    require_preflight(bundle, frozen)
    p = bundle.get("protocol")
    available = {
        "facts": [f["fact_id"] for f in bundle.facts],
        "models": p["models"],
        "budgets": p["budgets"],
        "variants": [v["id"] for v in p["variants"]],
    }
    selected = {}
    for name, value in (
        ("facts", facts),
        ("models", models),
        ("budgets", budgets),
        ("variants", variants),
    ):
        value = available[name] if value is None else value
        expected_type = int if name == "budgets" else str
        if (
            not isinstance(value, (list, tuple))
            or not value
            or any(type(item) is not expected_type for item in value)
        ):
            raise BenchmarkError("Invalid probe plan selection")
        if len(set(value)) != len(value):
            raise BenchmarkError("Invalid probe plan selection")
        if any(item not in available[name] for item in value):
            raise BenchmarkError("Probe selection is outside the frozen protocol")
        selected[name] = list(value)
    return Manifest(
        canonical_json({"schema_version": 1, "freeze": frozen, "protocol": p, **selected})
    )


def check_manifest(bundle: Bundle, frozen: dict, manifest: Manifest) -> None:
    try:
        data = manifest.data
        rebuilt = make_manifest(
            bundle, frozen, **{key: data[key] for key in ("facts", "models", "budgets", "variants")}
        )
        if rebuilt != manifest:
            raise BenchmarkError("Run manifest drift")
    except (KeyError, TypeError):
        raise BenchmarkError("Malformed run manifest") from None


def variant_options(bundle: Bundle, identifier: str) -> AssemblyOptions:
    for row in bundle.get("protocol")["variants"]:
        if row["id"] == identifier and row["window"]:
            return AssemblyOptions(
                **{key: row[key] for key in ("cap", "pins", "retrieve", "summarize")}
            )
    raise BenchmarkError("Unknown layered variant")
