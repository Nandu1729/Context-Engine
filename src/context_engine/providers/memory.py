"""Optional memory-aware inference; memory owns replay lifecycle, not the provider cache."""

import uuid
from dataclasses import asdict

from ..errors import ContractError, MemoryConflict, MemoryIntegrityError
from ..memory import MemoryStore
from .client import ProviderClient
from .contracts import Completion, ModelResult, fingerprint


class MemoryProvider:
    def __init__(self, memory: MemoryStore, client: ProviderClient, *, replay=False):
        if not isinstance(memory, MemoryStore) or not isinstance(client, ProviderClient):
            raise ContractError("Memory integration requires validated stores/client")
        if type(replay) is not bool or client.replay.enabled:
            raise ContractError(
                "Use memory-managed replay only; provider body cache must be disabled"
            )
        self.memory, self.client, self.replay = memory, client, replay

    async def complete(self, scope, question, budget, *, system, security_scope, **assembly):
        if not isinstance(security_scope, str) or not security_scope.strip():
            raise ContractError("An authorized security scope is required")
        snapshot, context = self.memory.assemble(scope, question, budget, system=system, **assembly)
        client = self.client
        key = fingerprint(
            {
                "snapshot": snapshot.snapshot_id,
                "request": context.request.to_wire(),
                "security": security_scope,
                "budget": asdict(budget),
                "generation": asdict(client.generation),
                "prices": asdict(client.prices),
                "account": client.quota.account_id,
                "counting": context.diagnostics.estimate.to_dict(),
                "transport": getattr(
                    client.transport, "namespace", type(client.transport).__qualname__
                ),
                "policy": "memory-provider-v1",
            }
        )
        if self.replay and (cached := self.memory.cache_get(snapshot, key)) is not None:
            try:
                completion = Completion.from_dict(cached["completion"])
                with client.store.transaction() as db:
                    source = db.execute(
                        "SELECT * FROM attempts WHERE id=?", (cached["attempt_id"],)
                    ).fetchone()
                    if (
                        source is None
                        or source["account"] != fingerprint(client.quota.account_id)
                        or source["state"] != "completed"
                        or source["request_key"] != cached["request_key"]
                        or source["completion_hash"] != fingerprint(completion.to_dict())
                        or source["cost"] != cached["cost"]
                    ):
                        raise MemoryIntegrityError("Memory replay ancestry is invalid")
                    db.execute(
                        "INSERT INTO events(id,account,request_key,created,kind,source_attempt,"
                        "new_cost) VALUES(?,?,?,?,?,?,0)",
                        (
                            uuid.uuid4().hex,
                            source["account"],
                            source["request_key"],
                            client.clock(),
                            "memory_replay",
                            source["id"],
                        ),
                    )
                self.memory.assert_current(snapshot)
                return ModelResult(
                    "replay",
                    cached["request_key"],
                    completion=completion,
                    replay_of=cached["attempt_id"],
                    new_cost_microusd=0,
                    original_cost_microusd=cached["cost"],
                )
            except (KeyError, TypeError, ValueError):
                raise MemoryIntegrityError("Malformed memory replay") from None
        result = await client.complete(
            context.request,
            budget,
            scope=scope,
            security_scope=security_scope,
            snapshot_revision=snapshot.snapshot_id,
            policy_version="memory-provider-v1",
        )
        try:
            self.memory.assert_current(snapshot)
            if self.replay and result.status == "success":
                self.memory.cache_put(
                    snapshot,
                    key,
                    {
                        "completion": result.completion.to_dict(),
                        "attempt_id": result.attempt_ids[-1],
                        "request_key": result.request_key,
                        "cost": result.original_cost_microusd,
                    },
                )
        except MemoryConflict:
            return ModelResult(
                "error",
                result.request_key,
                result.attempt_ids,
                error_code="memory_revision_conflict",
                new_cost_microusd=result.new_cost_microusd,
                warning="response_discarded_memory_changed",
            )
        return result
