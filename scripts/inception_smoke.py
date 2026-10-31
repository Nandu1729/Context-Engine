#!/usr/bin/env python3
"""One Inception (Mercury) smoke call; PAID, so it needs explicit owner approval.

`plan` (default) is offline. `run --allow-live` sends exactly one request: the
0.12.0 default assembly of one frozen synthetic fact at 900 tokens, mercury-3,
256 completion tokens, no retries, with a separate ledger and a hard daily spend
cap of 1000 micro-dollars ($0.001). Prints status JSON only (no prompt/answer text).
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from context_engine.evaluation.corpus import aliases, load_bundle
from context_engine.evaluation.grading import answer_correct
from context_engine.evaluation.strategies import assemble_strategy
from context_engine.providers.client import ProviderClient
from context_engine.providers.contracts import (
    InceptionGenerationConfig,
    PriceCard,
    QuotaPolicy,
    RetryConfig,
)
from context_engine.providers.credentials import private_bytes
from context_engine.providers.store import RuntimeStore

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output/private/inception-smoke-001"
LEDGER = ROOT / "output/private/inception-account.sqlite"
# Published mercury-3 launch prices on 2026-10-31 (USD per 1M): 0.10 / 0.01 / 0.35.
PRICES = PriceCard("inception-mercury-3-2026-10-31", 100_000, 10_000, 350_000)
POLICY = QuotaPolicy(
    account_id="inception-context-engine-v1",
    daily_budget_microusd=1000,
    rpm=10,
    tpm=100_000,
    rpd=1,
    tpd=10_000,
    billing_mode="metered",
)
GENERATION = InceptionGenerationConfig(model="mercury-3", max_completion_tokens=256)
RETRIES = RetryConfig(max_attempts=1, attempt_timeout=20, total_timeout=25)
FACT = "merchant"


def emit(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def inception_key(env_file=ROOT / ".env"):
    """Read only the INCEPTION_API_KEY line; never print it."""
    lines = private_bytes(env_file, 8192).decode("ascii").splitlines()
    values = [
        line.partition("=")[2].strip().strip("\"'")
        for line in lines
        if line.strip().partition("=")[0].strip() == "INCEPTION_API_KEY"
    ]
    if len(values) != 1 or not values[0] or any(c.isspace() for c in values[0]):
        raise ValueError("Missing or invalid INCEPTION_API_KEY; value is never displayed")
    return values[0]


def prepare():
    bundle = load_bundle()
    fact = bundle.fact(FACT)
    result, budget = assemble_strategy(bundle, fact, 900, "combined")
    scope = bundle.job(fact["question"]).arguments["pinned_facts"].scope
    return bundle, fact, result, budget, scope


async def send(client, result, budget, scope):
    return await client.complete(
        result.request,
        budget,
        scope=scope,
        security_scope="inception-smoke-001",
        snapshot_revision=result.diagnostics.input_fingerprint,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "run"), nargs="?", default="plan")
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    _, fact, result, budget, scope = prepare()
    estimate = result.diagnostics.estimate.estimated_tokens
    worst = PRICES.reserve_cost(estimate, GENERATION.max_completion_tokens)
    if args.command == "plan":
        emit(
            {
                "status": "PLANNED",
                "calls": 1,
                "model": GENERATION.model,
                "estimated_input_tokens": estimate,
                "max_cost_microusd": worst,
                "spend_cap_microusd": POLICY.daily_budget_microusd,
                "already_run": RUN.exists(),
            }
        )
        return 0
    if not args.allow_live or worst > POLICY.daily_budget_microusd:
        emit({"status": "REFUSED"})
        return 1
    RUN.mkdir(mode=0o700, parents=False, exist_ok=False)  # One attempt, ever.
    client = ProviderClient(
        store=RuntimeStore(LEDGER),
        quota=POLICY,
        prices=PRICES,
        api_key=inception_key(),
        generation=GENERATION,
        retries=RETRIES,
    )
    outcome = asyncio.run(send(client, result, budget, scope))
    receipt = RUN / "receipt.json"
    with receipt.open("x", encoding="utf-8") as handle:
        json.dump(outcome.to_dict(include_content=True), handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    usage = outcome.completion.usage if outcome.completion else None
    emit(
        {
            "status": outcome.status,
            "error_code": outcome.error_code,
            "cost_microusd": outcome.new_cost_microusd,
            "input_tokens": usage.input_tokens if usage else None,
            "output_tokens": usage.output_tokens if usage else None,
            "correct": bool(
                outcome.completion and answer_correct(outcome.completion.content, aliases(fact))
            ),
        }
    )
    return int(outcome.status != "success")


if __name__ == "__main__":
    raise SystemExit(main())
