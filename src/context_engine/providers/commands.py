"""Explicit live probe and an entirely synthetic accounting demonstration."""

import asyncio
import os
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from ..config import BudgetConfig, Settings
from ..errors import ContractError
from ..inspection import demo_job, load_job
from ..models import ChatRequest, Message, Role, Scope
from ..tokens import TiktokenCounter
from .client import ProviderClient
from .contracts import Completion, GenerationConfig, PriceCard, QuotaPolicy, ReplayPolicy, Usage
from .store import RuntimeStore


class SyntheticTransport:
    namespace = "c05-offline-demo-v1"

    def __init__(self):
        self.calls = 0

    async def send(self, payload, api_key, timeout):
        self.calls += 1
        return Completion(
            payload["model"],
            f"synthetic-{self.calls}",
            "synthetic-answer",
            "stop",
            Usage(40, 5, cached_input_tokens=4, reasoning_tokens=2),
        )


async def _demo(directory: Path) -> dict:
    store = RuntimeStore(directory / "runtime.sqlite")
    quota = QuotaPolicy("synthetic-demo", 10000, rpd=2)
    transport = SyntheticTransport()
    client = ProviderClient(
        store=store,
        quota=quota,
        prices=PriceCard("synthetic-v1", 1000000, 500000, 2000000),
        transport=transport,
        api_key="synthetic-not-a-credential",
        replay=ReplayPolicy(enabled=True),
    )
    request = ChatRequest((Message("q", Role.USER, "Synthetic question one?"),))
    options = dict(
        scope=Scope("demo", "demo"), security_scope="synthetic-v1", snapshot_revision="synthetic-v1"
    )
    budget = BudgetConfig(input_cap=900)
    first = await client.complete(request, budget, **options)
    replay = await client.complete(request, budget, **options)
    changed = ChatRequest((Message("q", Role.USER, "Synthetic question two?"),))
    miss = await client.complete(changed, budget, **options)
    client.generation = replace(client.generation, temperature=0.5)
    blocked = await client.complete(changed, budget, **options)
    results = dict(
        first=first.to_dict(),
        identical_replay=replay.to_dict(),
        changed_question=miss.to_dict(),
        changed_generation=blocked.to_dict(),
    )
    valid = (
        first.status == miss.status == "success"
        and replay.status == "replay"
        and replay.new_cost_microusd == 0
        and blocked.error_code == "quota_exhausted"
        and blocked.request_key != miss.request_key
        and transport.calls == 2
    )
    return dict(
        mode="offline_provider_demo",
        status="PASS" if valid else "FAIL",
        real_inference_calls=0,
        simulated_transport_calls=transport.calls,
        pricing="synthetic; not provider pricing or billing evidence",
        results=results,
        ledger=store.snapshot(quota),
    )


def provider_demo() -> dict:
    with TemporaryDirectory(prefix="context-provider-demo-") as directory:
        return asyncio.run(_demo(Path(directory)))


def provider_probe(args) -> dict:
    # All authorization/config checks precede the first file mutation or network operation.
    if not args.allow_live or args.daily_budget_microusd <= 0:
        raise ContractError("Live probe requires --allow-live and a positive explicit spending cap")
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or any(ord(c) < 33 or ord(c) > 126 for c in api_key):
        raise ContractError("Live probe requires a valid GROQ_API_KEY environment variable")
    quota = QuotaPolicy(
        args.account_id,
        args.daily_budget_microusd,
        rpm=args.rpm,
        tpm=args.tpm,
        rpd=args.rpd,
        tpd=args.tpd,
    )
    prices = PriceCard(
        args.price_version,
        args.input_rate_microusd,
        args.cached_input_rate_microusd,
        args.output_rate_microusd,
    )
    settings = Settings.from_env()
    job = load_job(args.input, settings) if args.input is not None else demo_job(settings)
    generation = GenerationConfig(
        model=args.model, max_completion_tokens=job.arguments["budget"].completion_reservation
    )
    assembled = job.run()
    client = ProviderClient(
        store=RuntimeStore(args.ledger),
        quota=quota,
        prices=prices,
        api_key=api_key,
        generation=generation,
        counter=TiktokenCounter(job.tokenizer),
    )
    result = asyncio.run(
        client.complete(
            assembled.request,
            job.arguments["budget"],
            scope=job.arguments["pinned_facts"].scope,
            security_scope=args.security_scope,
            snapshot_revision=args.snapshot_revision,
        )
    )
    return dict(
        mode="live_provider_probe",
        synthetic_input=job.synthetic,
        **result.to_dict(include_content=args.show_content),
    )
