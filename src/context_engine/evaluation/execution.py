"""Durable, single-dispatch benchmark execution; never obtains answers from grading truth."""

import json
from dataclasses import asdict
from importlib import metadata
from pathlib import Path

from ..config import BudgetConfig, TokenizerConfig
from ..errors import BenchmarkError, ContextEngineError
from ..models import ChatRequest, Message, ToolCall, ToolDefinition, canonical_json
from ..providers.client import ProviderClient
from ..providers.contracts import (
    ADAPTER_VERSION,
    ENDPOINT,
    Completion,
    GenerationConfig,
    PriceCard,
    QuotaPolicy,
    ReplayPolicy,
    RetryConfig,
    Usage,
    fingerprint,
)
from ..providers.store import RuntimeStore
from ..providers.transport import GroqTransport
from .corpus import strict_json
from .harness import _prepare_validated
from .protocol import Manifest, check_manifest
from .results import MAX_RUN_BYTES, RESPONSE_FIELDS, record_response, validate_run

PROVIDER_DEPENDENCIES = ("httpx", "httpcore", "h11", "anyio", "typing-extensions")


def expected_request_key(row, profile, execution_id, scope, protocol):
    configured = profile["clients"][row["model"]]
    budget = BudgetConfig(
        input_cap=row["budget"],
        completion_reservation=protocol["generation"]["max_completion_tokens"],
        **protocol["budget"],
    )
    return fingerprint(
        {
            "adapter": profile["adapter"],
            "endpoint": profile["endpoint"],
            "payload": GenerationConfig(**configured["generation"]).to_wire(
                request_from_wire(row["request"])
            ),
            "account": configured["quota"]["account_id"],
            "scope": scope,
            "security_scope": profile["security_scope"],
            "snapshot_revision": profile["snapshot_revision"],
            "policy_version": execution_id,
            "budget": asdict(budget),
            "counting": row["estimate"],
            "prices": configured["prices"],
            "transport": configured["transport"],
        }
    )


def dependency_profile():
    result = {}
    for name in PROVIDER_DEPENDENCIES:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = None
    return result


def execution_profile(manifest, clients, *, mode, max_run_cost_microusd):
    if mode not in ("offline", "live") or type(max_run_cost_microusd) is not int:
        raise BenchmarkError("Invalid execution mode or run spending cap")
    if max_run_cost_microusd < 0 or max_run_cost_microusd > 10**12:
        raise BenchmarkError("An explicit bounded run spending cap is required")
    if set(clients) != set(manifest.data["models"]):
        raise BenchmarkError("Every selected model requires its own configured client")
    profiles = {}
    for model, client in clients.items():
        if not isinstance(client, ProviderClient):
            raise BenchmarkError("Execution requires the controlled provider client")
        client.quota.validate_prices(client.prices)
        if (client.quota.billing_mode == "free_tier") != (max_run_cost_microusd == 0):
            raise BenchmarkError("Only explicit free-tier accounts permit a zero run spending cap")
        if asdict(client.generation) != dict(
            model=model, tool_choice="none", **manifest.data["protocol"]["generation"]
        ):
            raise BenchmarkError("Generation differs from the frozen protocol")
        real = type(client.transport) is GroqTransport and client.transport.http_transport is None
        if real != (mode == "live"):
            raise BenchmarkError("Live and synthetic transports must not share provenance")
        if client.counter.config != TokenizerConfig(**manifest.data["protocol"]["tokenizer"]):
            raise BenchmarkError("Provider tokenizer differs from the frozen protocol")
        profiles[model] = {
            "quota": asdict(client.quota),
            "prices": asdict(client.prices),
            "generation": asdict(client.generation),
            "retry": asdict(client.retries),
            "replay": asdict(client.replay),
            "transport": client.transport.namespace,
            "ledger_path": str(client.store.path),
        }
    policies = {(p["ledger_path"], canonical_json(p["quota"])) for p in profiles.values()}
    if len(policies) != 1:
        raise BenchmarkError("All models must share one account, ledger and quota policy")
    return {
        "mode": mode,
        "adapter": ADAPTER_VERSION,
        "endpoint": ENDPOINT,
        "dependencies": dependency_profile(),
        "clients": profiles,
        "max_run_cost_microusd": max_run_cost_microusd,
        "security_scope": "synthetic-benchmark-v1",
        "snapshot_revision": manifest.data["freeze"]["fixture_hashes"]["scenario"],
    }


def request_from_wire(value):
    messages = []
    for index, raw in enumerate(value["messages"]):
        calls = tuple(
            ToolCall(c["id"], c["function"]["name"], c["function"]["arguments"])
            for c in raw.get("tool_calls", ())
        )
        messages.append(
            Message(
                f"benchmark:{index}",
                raw["role"],
                raw.get("content", ""),
                raw.get("tool_call_id"),
                calls,
            )
        )
    tools = tuple(
        ToolDefinition(
            t["function"]["name"],
            t["function"].get("description", ""),
            canonical_json(t["function"]["parameters"]),
        )
        for t in value.get("tools", ())
    )
    return ChatRequest(tuple(messages), tools)


def bind_response(bundle, prepared, receipt, mode):
    result = receipt["result"]
    completion = Completion.from_dict(result["completion"]) if result["completion"] else None
    origin = "test" if mode == "offline" else ("replay" if result["replay_of"] else "live")
    finish = (
        "stop"
        if result["status"] in ("success", "replay")
        else ("length" if result["status"] == "truncated" else "error")
    )
    usage = None
    if completion and completion.usage.cached_input_tokens is not None:
        u = completion.usage
        usage = dict(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cached_input_tokens=u.cached_input_tokens,
        )
    code = result["error_code"]
    code = (
        code
        if code in ("timeout", "transport", "rate_limit", "invalid_response")
        else "provider_error"
    )
    return record_response(
        bundle,
        prepared,
        answer=completion.content if finish != "error" else None,
        finish_reason=finish,
        origin=origin,
        error_code=code if finish == "error" else None,
        provider_request_id=completion.response_id if completion else None,
        replay_of=result["replay_of"] if origin == "replay" else None,
        provider_usage=usage,
    )


def verify_receipt(receipt, model, profile):
    """Cross-check adapter results against captured ledger rows, not a claimed label."""
    r, rows = receipt["result"], receipt["ledger_rows"]
    if set(receipt) != {"result", "ledger_rows"} or not isinstance(rows, list):
        raise BenchmarkError("Malformed adapter receipt")
    ids = list(r["attempt_ids"])
    expected = set(ids + ([r["replay_of"]] if r["replay_of"] else []))
    if (
        len(ids) != len(set(ids))
        or {a["id"] for a in rows} != expected
        or len(rows) != len(expected)
    ):
        raise BenchmarkError("Receipt attempt ancestry mismatch")
    for a in rows:
        RuntimeStore._validate_row(a)
        if a["usage_json"]:
            usage = Usage(**json.loads(a["usage_json"]))
            price = PriceCard(**json.loads(a["price_json"]))
            if a["cost"] != price.observed_cost(usage) or a["charged_tokens"] != usage.total_tokens:
                raise BenchmarkError("Ledger usage and calculated cost disagree")
        if (
            a["model"] != model
            or a["request_key"] != r["request_key"]
            or a["account"] != fingerprint(profile["clients"][model]["quota"]["account_id"])
            or json.loads(a["price_json"]) != profile["clients"][model]["prices"]
        ):
            raise BenchmarkError("Receipt ledger scope or pricing mismatch")
    own = [a for a in rows if a["id"] in ids]
    expected_cost = None if any(a["cost"] is None for a in own) else sum(a["cost"] for a in own)
    if r["new_cost_microusd"] != expected_cost:
        raise BenchmarkError("Receipt cost differs from attempt accounting")
    if r["status"] == "replay":
        if not r["replay_of"] or ids or r["new_cost_microusd"] != 0:
            raise BenchmarkError("Replay must have ancestry and zero new spend")
    elif r["replay_of"] is not None:
        raise BenchmarkError("Non-replay has replay ancestry")
    if r["completion"] is not None:
        c = Completion.from_dict(r["completion"])
        if c.model != model or not rows:
            raise BenchmarkError("Completion model or ledger receipt missing")
        source_id = r["replay_of"] or ids[-1]
        source = next(a for a in rows if a["id"] == source_id)
        if (
            source["completion_hash"] != fingerprint(c.to_dict())
            or json.loads(source["usage_json"]) != asdict(c.usage)
            or source["cost"] != r["original_cost_microusd"]
        ):
            raise BenchmarkError("Completion content or usage differs from ledger receipt")
        expected_status = {
            "stop": "success",
            "length": "truncated",
            "tool_calls": "tool_calls",
            "content_filter": "filtered",
        }[c.finish_reason]
        if r["status"] not in (expected_status, "replay"):
            raise BenchmarkError("Completion status mismatch")
        if r["status"] == "replay" and c.finish_reason != "stop":
            raise BenchmarkError("Partial completion cannot be replayed")
    elif r["status"] != "error":
        raise BenchmarkError("Successful outcome lacks completion")


class RunJournal:
    """Single-dispatch journal; unknown intents require operator recovery, never auto-resend."""

    def __init__(self, path: Path, manifest: Manifest, profile: dict):
        self.manifest, self.profile = manifest, profile
        self.identity = {"manifest": manifest.data, "profile": profile}
        self.execution_id = fingerprint(self.identity)
        if str(Path(path).absolute()) in {p["ledger_path"] for p in profile["clients"].values()}:
            raise BenchmarkError("Execution journal and provider ledger must be separate files")
        self.store = RuntimeStore(path)
        with self.store.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS benchmark_identity(payload TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS benchmark_probes(
                id TEXT PRIMARY KEY, phase TEXT NOT NULL, record TEXT NOT NULL,
                receipt TEXT, reserved_cost INTEGER NOT NULL DEFAULT 0)""")
            previous = db.execute("SELECT payload FROM benchmark_identity").fetchall()
            if previous and (len(previous) != 1 or previous[0][0] != canonical_json(self.identity)):
                raise BenchmarkError("Execution identity drift; cannot resume this journal")
            if not previous:
                db.execute(
                    "INSERT INTO benchmark_identity VALUES(?)", (canonical_json(self.identity),)
                )

    def snapshot(self):
        with self.store.transaction() as db:
            values = db.execute("SELECT * FROM benchmark_probes ORDER BY id").fetchall()
        return [
            {
                "probe_id": r["id"],
                "phase": r["phase"],
                "record": strict_json(r["record"]),
                "receipt": strict_json(r["receipt"]) if r["receipt"] else None,
                "reserved_cost": r["reserved_cost"],
            }
            for r in values
        ]

    def prepare(self, row):
        with self.store.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO benchmark_probes(id,phase,record) VALUES(?,?,?)",
                (
                    row["probe_id"],
                    "done" if row["state"] == "non_fit" else "pending",
                    canonical_json(row),
                ),
            )

    def claim(self, identifier, reserved_cost):
        with self.store.transaction() as db:
            rows = db.execute("SELECT * FROM benchmark_probes").fetchall()
            if any(r["phase"] == "dispatching" for r in rows):
                return "uncertain_dispatch"
            charged = 0
            for r in rows:
                receipt = strict_json(r["receipt"]) if r["receipt"] else None
                cost = receipt["result"]["new_cost_microusd"] if receipt else 0
                if cost is None:
                    return "uncertain_usage"
                charged += cost
            if charged + reserved_cost > self.profile["max_run_cost_microusd"]:
                return "run_budget"
            if (
                db.execute(
                    "UPDATE benchmark_probes SET phase='dispatching',reserved_cost=? "
                    "WHERE id=? AND phase='pending'",
                    (reserved_cost, identifier),
                ).rowcount
                != 1
            ):
                return "already_claimed"
            return None

    def finish(self, identifier, row, receipt, *, deferred=False):
        with self.store.transaction() as db:
            if (
                db.execute(
                    "UPDATE benchmark_probes SET phase=?,record=?,receipt=? "
                    "WHERE id=? AND phase='dispatching'",
                    (
                        "pending" if deferred else "done",
                        canonical_json(row),
                        canonical_json(receipt) if receipt else None,
                        identifier,
                    ),
                ).rowcount
                != 1
            ):
                raise BenchmarkError("Dispatch intent lost; accounting requires review")


def validate_execution(bundle, frozen, payload):
    try:
        if set(payload) != {
            "schema_version",
            "execution_id",
            "manifest",
            "profile",
            "entries",
            "digest",
        }:
            raise BenchmarkError("Unexpected execution snapshot fields")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 2:
            raise BenchmarkError("Unsupported execution snapshot")
        if payload["digest"] != fingerprint({k: v for k, v in payload.items() if k != "digest"}):
            raise BenchmarkError("Execution snapshot digest mismatch")
        manifest = Manifest(canonical_json(payload["manifest"]))
        check_manifest(bundle, frozen, manifest)
        profile = payload["profile"]
        if payload["execution_id"] != fingerprint({"manifest": manifest.data, "profile": profile}):
            raise BenchmarkError("Execution identity mismatch")
        if profile["mode"] not in ("offline", "live"):
            raise BenchmarkError("Unknown execution provenance")
        if profile["adapter"] != ADAPTER_VERSION or profile["endpoint"] != ENDPOINT:
            raise BenchmarkError("Unsupported provider profile")
        if set(profile["clients"]) != set(manifest.data["models"]):
            raise BenchmarkError("Profile model selection mismatch")
        maximum = profile["max_run_cost_microusd"]
        if type(maximum) is not int or not 0 <= maximum <= 10**12:
            raise BenchmarkError("Invalid recorded run spending cap")
        for model, config in profile["clients"].items():
            quota = QuotaPolicy(**config["quota"])
            quota.validate_prices(PriceCard(**config["prices"]))
            if (quota.billing_mode == "free_tier") != (maximum == 0):
                raise BenchmarkError("Recorded free-tier policy and spending cap disagree")
            RetryConfig(**config["retry"])
            ReplayPolicy(**config["replay"])
            if asdict(GenerationConfig(**config["generation"])) != dict(
                model=model, tool_choice="none", **manifest.data["protocol"]["generation"]
            ):
                raise BenchmarkError("Profile generation drift")
            if config["transport"].startswith("groq-live-") != (profile["mode"] == "live"):
                raise BenchmarkError("Transport provenance mismatch")
        rows = []
        for entry in payload["entries"]:
            row, receipt = entry["record"], entry["receipt"]
            if entry["probe_id"] != row["probe_id"] or entry["phase"] not in (
                "done",
                "pending",
                "dispatching",
            ):
                raise BenchmarkError("Journal state mismatch")
            if type(entry["reserved_cost"]) is not int or entry["reserved_cost"] < 0:
                raise BenchmarkError("Invalid reservation")
            if receipt:
                verify_receipt(receipt, row["model"], profile)
                key = expected_request_key(
                    row,
                    profile,
                    payload["execution_id"],
                    bundle.get("scenario")["scope"],
                    manifest.data["protocol"],
                )
                if receipt["result"]["request_key"] != key:
                    raise BenchmarkError("Receipt belongs to a different assembled request")
                prepared = {**row, **dict.fromkeys(RESPONSE_FIELDS), "state": "prepared"}
                if (
                    bind_response(bundle, prepared, receipt, profile["mode"]) != row
                    or entry["phase"] != "done"
                ):
                    raise BenchmarkError("Adapter receipt differs from graded record")
            elif row["state"] not in ("non_fit", "prepared"):
                raise BenchmarkError("Outcome lacks adapter evidence")
            if (entry["phase"] == "done") != (row["state"] != "prepared"):
                raise BenchmarkError("Terminal journal state mismatch")
            rows.append(row)
        validation = validate_run(bundle, frozen, manifest, rows)
        if any(g["status"] == "FAIL" and g["gate"] != "V4" for g in validation["gates"]):
            raise BenchmarkError("Execution snapshot failed integrity gates")
        return manifest, rows, validation
    except BenchmarkError:
        raise
    except (ContextEngineError, KeyError, TypeError, ValueError, IndexError, StopIteration):
        raise BenchmarkError("Malformed execution snapshot") from None


def execution_snapshot(journal):
    payload = {
        "schema_version": 2,
        "execution_id": journal.execution_id,
        **journal.identity,
        "entries": journal.snapshot(),
    }
    return {**payload, "digest": fingerprint(payload)}


def load_execution(path, bundle, frozen):
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(MAX_RUN_BYTES + 1)
        payload = strict_json(raw.decode("utf-8"), maximum=MAX_RUN_BYTES)
        validate_execution(bundle, frozen, payload)
        return payload
    except (OSError, UnicodeError):
        raise BenchmarkError("Cannot read execution snapshot") from None


def save_execution(path, payload):
    """Bounded compact export; indentation must not expand the full 744-slot evidence."""
    raw = (canonical_json(payload) + "\n").encode("utf-8")
    if len(raw) > MAX_RUN_BYTES:
        raise BenchmarkError("Snapshot exceeds export limit; journal remains recoverable")
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(raw)
    except OSError:
        raise BenchmarkError("Snapshot destination must be a new writable file") from None


async def execute(bundle, frozen, journal, clients, *, max_calls=744, allow_live=False):
    check_manifest(bundle, frozen, journal.manifest)
    profile = execution_profile(
        journal.manifest,
        clients,
        mode=journal.profile["mode"],
        max_run_cost_microusd=journal.profile["max_run_cost_microusd"],
    )
    if profile != journal.profile:
        raise BenchmarkError("Provider execution profile drift")
    if type(max_calls) is not int or not 0 <= max_calls <= 744:
        raise BenchmarkError("Execution call batch must be within 0..744")
    if profile["mode"] == "live" and (
        not allow_live or journal.manifest.data["protocol"]["approval"] != "owner_approved"
    ):
        raise BenchmarkError("Live benchmark requires authorization and approved registration")
    payload = execution_snapshot(journal)
    validate_execution(bundle, frozen, payload)
    existing = {e["probe_id"]: e for e in payload["entries"]}
    if any(e["phase"] == "dispatching" for e in existing.values()):
        return {"status": "PAUSED", "reason": "uncertain_dispatch", "calls": 0}
    calls = 0
    # Contexts do not depend on model identity; reuse only within this immutable batch.
    prepared_cache = {}
    for slot in journal.manifest.slots:
        entry = existing.get(slot["probe_id"])
        if entry and entry["phase"] == "done":
            continue
        key = (slot["budget"], slot["variant"], slot["fact_id"])
        if entry:
            prepared = entry["record"]
        elif key in prepared_cache:
            prepared = {**prepared_cache[key], **slot}
        else:
            prepared = _prepare_validated(bundle, slot)
            prepared_cache[key] = prepared
        journal.prepare(prepared)
        if prepared["state"] == "non_fit":
            continue
        if calls >= max_calls:
            return {"status": "PAUSED", "reason": "batch_limit", "calls": calls}
        client = clients[slot["model"]]
        request = request_from_wire(prepared["request"])
        if client.counter.count_request(request).to_dict() != prepared["estimate"]:
            raise BenchmarkError("Provider counter or request serialization drift before dispatch")
        reservation = client.prices.reserve_cost(
            prepared["estimate"]["estimated_tokens"], client.generation.max_completion_tokens
        )
        blocked = journal.claim(slot["probe_id"], reservation)
        if blocked:
            return {"status": "PAUSED", "reason": blocked, "calls": calls}
        p = journal.manifest.data["protocol"]
        budget = BudgetConfig(
            input_cap=slot["budget"],
            completion_reservation=p["generation"]["max_completion_tokens"],
            **p["budget"],
        )
        request = request_from_wire(prepared["request"])
        scope = bundle.job(bundle.fact(slot["fact_id"])["question"]).arguments["pinned_facts"].scope
        # Cancellation/crash preserves the committed intent; it must never be blindly redelivered.
        result = await client.complete(
            request,
            budget,
            scope=scope,
            security_scope=profile["security_scope"],
            snapshot_revision=profile["snapshot_revision"],
            policy_version=journal.execution_id,
        )
        if result.error_code == "quota_exhausted" and not result.attempt_ids:
            journal.finish(slot["probe_id"], prepared, None, deferred=True)
            return {"status": "PAUSED", "reason": "quota", "calls": calls}
        calls += 1
        ids = set(result.attempt_ids) | ({result.replay_of} if result.replay_of else set())
        receipt = {
            "result": result.to_dict(include_content=True),
            "ledger_rows": [
                a for a in client.store.snapshot(client.quota)["attempts"] if a["id"] in ids
            ],
        }
        verify_receipt(receipt, slot["model"], profile)
        row = bind_response(bundle, prepared, receipt, profile["mode"])
        journal.finish(slot["probe_id"], row, receipt)
        if result.new_cost_microusd is None:
            return {"status": "PAUSED", "reason": "uncertain_usage", "calls": calls}
    return {"status": "FINISHED", "reason": "all_slots_disposed", "calls": calls}
