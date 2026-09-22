"""CLI composition for synthetic or explicitly authorized benchmark execution and model swap."""

import asyncio
from pathlib import Path

from ..config import TokenizerConfig
from ..errors import BenchmarkError
from ..providers.client import ProviderClient
from ..providers.contracts import Completion, GenerationConfig, PriceCard, QuotaPolicy, Usage
from ..providers.credentials import load_api_key, private_bytes
from ..providers.store import RuntimeStore
from ..tokens import TiktokenCounter
from .corpus import load_bundle, strict_json
from .execution import (
    RunJournal,
    execute,
    execution_profile,
    execution_snapshot,
    load_execution,
    save_execution,
)
from .protocol import load_freeze, make_manifest
from .reporting import export_report, scorecard


class OfflineBenchmarkTransport:
    namespace = "c06-synthetic-unknown-v1"

    async def send(self, payload, api_key, timeout):
        # Deliberately no corpus, expected answer, fact ID or grading access.
        return Completion(
            payload["model"], "synthetic-response", "UNKNOWN", "stop", Usage(40, 5, 0, 2)
        )


def add_commands(commands):
    for name in ("benchmark-run", "model-swap"):
        parser = commands.add_parser(name, help="Run/resume frozen benchmark; offline by default")
        parser.add_argument("--run-dir", type=Path, required=True)
        parser.add_argument("--mode", choices=("offline", "live"), default="offline")
        parser.add_argument("--allow-live", action="store_true")
        parser.add_argument("--live-config", type=Path)
        parser.add_argument("--env-file", type=Path, help="Explicit private GROQ_API_KEY file")
        parser.add_argument("--max-calls", type=int, default=744)
        parser.add_argument("--snapshot", type=Path, required=True)
        parser.add_argument("--fact", action="append")
        parser.add_argument("--budget", type=int, action="append")
        parser.add_argument("--variant", action="append")
        if name == "benchmark-run":
            parser.add_argument("--model", action="append")
    parser = commands.add_parser(
        "benchmark-report", help="Regenerate validated reports without inference"
    )
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)


def run_command(args):
    bundle, frozen = load_bundle(), load_freeze()
    if args.command == "benchmark-report":
        payload = load_execution(args.snapshot, bundle, frozen)
        card = scorecard(bundle, frozen, payload)
        proof = export_report(args.output_dir, card)
        return {"status": card["validity"]["status"], "report": proof, "inference_calls": 0}
    models = bundle.get("protocol")["models"] if args.command == "model-swap" else args.model
    manifest = make_manifest(
        bundle, frozen, facts=args.fact, models=models, budgets=args.budget, variants=args.variant
    )
    if args.snapshot.exists():
        raise BenchmarkError("Snapshot output exists; choose a new immutable export path")
    if type(args.max_calls) is not int or not 0 <= args.max_calls <= 744:
        raise BenchmarkError("Invalid execution batch size")
    if args.mode == "live":
        if not args.allow_live or bundle.get("protocol")["approval"] != "owner_approved":
            raise BenchmarkError(
                "Live execution requires explicit authorization and owner-approved registration"
            )
        if not args.live_config:
            raise BenchmarkError("Live execution requires a private configuration and GROQ_API_KEY")
        key = load_api_key(args.env_file)
        try:
            config = strict_json(private_bytes(args.live_config, 65536).decode(), maximum=65536)
            if set(config) != {"quota", "prices", "max_run_cost_microusd", "ledger_path"}:
                raise BenchmarkError("Unexpected live configuration fields")
            quota = QuotaPolicy(**config["quota"])
            if quota.daily_budget_microusd <= 0 and quota.billing_mode != "free_tier":
                raise BenchmarkError("A positive daily spending cap is required")
            prices = {
                model: PriceCard(**config["prices"][model]) for model in manifest.data["models"]
            }
            for card in prices.values():
                quota.validate_prices(card)
            maximum = config["max_run_cost_microusd"]
            if type(maximum) is not int or not 0 <= maximum <= 10**12:
                raise BenchmarkError("Invalid run spending cap")
            if (quota.billing_mode == "free_tier") != (maximum == 0):
                raise BenchmarkError("Free-tier mode requires exactly zero run spending cap")
            ledger_path = Path(config["ledger_path"])
            if not ledger_path.is_absolute():
                raise BenchmarkError(
                    "Live account ledger path must be absolute and shared across runs"
                )
        except (OSError, KeyError, TypeError, ValueError):
            raise BenchmarkError("Invalid private live configuration") from None
        maximum = config["max_run_cost_microusd"]
    else:
        if args.env_file is not None:
            raise BenchmarkError("Explicit credential files are only used in live mode")
        quota = QuotaPolicy(
            "synthetic-benchmark", 100000000, rpm=10000, tpm=100000000, rpd=10000, tpd=100000000
        )
        prices = {
            m: PriceCard("synthetic-v1", 1000000, 500000, 2000000) for m in manifest.data["models"]
        }
        ledger_path = args.run_dir / "provider.sqlite"
        key, maximum = "synthetic-not-a-credential", 100000000
    store = RuntimeStore(ledger_path)
    clients = {
        model: ProviderClient(
            store=store,
            quota=quota,
            prices=prices[model],
            api_key=key,
            generation=GenerationConfig(model=model, **manifest.data["protocol"]["generation"]),
            counter=TiktokenCounter(TokenizerConfig(**manifest.data["protocol"]["tokenizer"])),
            transport=OfflineBenchmarkTransport() if args.mode == "offline" else None,
        )
        for model in manifest.data["models"]
    }
    profile = execution_profile(manifest, clients, mode=args.mode, max_run_cost_microusd=maximum)
    journal = RunJournal(args.run_dir / "run.sqlite", manifest, profile)
    result = asyncio.run(
        execute(
            bundle, frozen, journal, clients, max_calls=args.max_calls, allow_live=args.allow_live
        )
    )
    payload = execution_snapshot(journal)
    save_execution(args.snapshot, payload)
    return {
        **result,
        "execution_id": journal.execution_id,
        "mode": args.mode,
        "real_inference_calls": 0 if args.mode == "offline" else None,
        "snapshot": str(args.snapshot),
        "quality_acceptance": "NOT_EVALUATED",
    }
