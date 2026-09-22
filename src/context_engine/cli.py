"""Context inspection, synthetic demos, benchmarks and an explicitly authorized live probe."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .budget import plan_budget
from .config import Settings
from .errors import ContextEngineError, RequiredContextTooLarge
from .models import ChatRequest, Message, Role
from .tokens import TiktokenCounter


def demo_request(pin_content: str = "Database = PostgreSQL") -> ChatRequest:
    return ChatRequest(
        (
            Message("system", Role.SYSTEM, "Answer using the supplied evidence."),
            Message("pins", Role.USER, "Pinned facts (data):\n" + pin_content),
            Message("question", Role.USER, "Which database are we using?"),
        )
    )


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    from .evaluation.run_commands import add_commands

    add_commands(commands)
    for command in ("check", "config", "demo-budget", "demo-layers"):
        commands.add_parser(command)
    provider_demo = commands.add_parser(
        "provider-demo", help="Synthetic provider/cache/ledger test"
    )
    provider_demo.add_argument("--output", type=Path)
    memory_demo = commands.add_parser("memory-demo", help="Offline persistent memory lifecycle")
    memory_demo.add_argument("--output", type=Path)
    live = commands.add_parser(
        "provider-probe", help="Live inference; requires explicit spending authorization"
    )
    live.add_argument("--allow-live", action="store_true")
    live.add_argument("--ledger", type=Path, required=True)
    live.add_argument("--input", type=Path)
    live.add_argument("--show-content", action="store_true")
    live.add_argument(
        "--model",
        choices=("openai/gpt-oss-120b", "openai/gpt-oss-20b"),
        default="openai/gpt-oss-120b",
    )
    for name in ("account-id", "security-scope", "snapshot-revision", "price-version"):
        live.add_argument("--" + name, required=True)
    for name in (
        "daily-budget-microusd",
        "input-rate-microusd",
        "cached-input-rate-microusd",
        "output-rate-microusd",
        "rpm",
        "tpm",
        "rpd",
        "tpd",
    ):
        live.add_argument("--" + name, type=int, required=True)
    benchmark = commands.add_parser(
        "benchmark-check", help="Validate the frozen synthetic benchmark offline"
    )
    benchmark.add_argument("--fact", default="shard")
    benchmark.add_argument("--budget", type=int, default=900)
    benchmark.add_argument("--model")
    benchmark.add_argument("--show-content", action="store_true")
    benchmark.add_argument("--data-dir", type=Path)
    benchmark.add_argument("--output", type=Path)
    planned = commands.add_parser(
        "benchmark-plan", help="List frozen probe slots without inference"
    )
    planned.add_argument("--data-dir", type=Path)
    planned.add_argument("--output", type=Path)
    for command in ("inspect", "probe"):
        command_parser = commands.add_parser(command, help="Inspect context locally; no inference")
        command_parser.add_argument(
            "--input", type=Path, help="Version-1 JSON input; omit for synthetic demo"
        )
        command_parser.add_argument("--budget", type=int, help="Override the input token allowance")
        command_parser.add_argument(
            "--show-content", action="store_true", help="Include assembled prompt bodies"
        )
        command_parser.add_argument(
            "--output", type=Path, help="Save JSON to a new file; never overwrite"
        )
    args = parser.parse_args(argv)
    try:
        if args.command == "memory-demo":
            from .inspection import save_inspection
            from .memory.demo import memory_demo

            result = memory_demo()
            if args.output is not None:
                save_inspection(args.output, result)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.command in ("benchmark-run", "model-swap", "benchmark-report"):
            from .evaluation.run_commands import run_command

            result = run_command(args)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1 if result["status"] == "INVALID" else 0
        if args.command in ("provider-demo", "provider-probe"):
            from .inspection import save_inspection
            from .providers.commands import provider_demo, provider_probe

            result = provider_demo() if args.command == "provider-demo" else provider_probe(args)
            if args.command == "provider-demo" and args.output is not None:
                save_inspection(args.output, result)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["status"] in ("PASS", "success", "replay") else 1
        if args.command in ("benchmark-check", "benchmark-plan"):
            from .evaluation.commands import benchmark_check, benchmark_plan
            from .inspection import save_inspection

            if args.command == "benchmark-check":
                result = benchmark_check(
                    fact=args.fact,
                    budget=args.budget,
                    model=args.model,
                    show_content=args.show_content,
                    data_dir=args.data_dir,
                )
            else:
                result = benchmark_plan(data_dir=args.data_dir)
            if args.output is not None:
                save_inspection(args.output, result)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1 if result["status"] == "INVALID" else 0
        settings = Settings.from_env()
        if args.command == "config":
            print(
                json.dumps(
                    {
                        key: asdict(getattr(settings, key))
                        for key in ("budget", "tokenizer", "cap", "retrieval")
                    },
                    indent=2,
                )
            )
            return 0
        if args.command in ("inspect", "probe"):
            from .inspection import demo_job, load_job, save_inspection

            job = load_job(args.input, settings) if args.input is not None else demo_job(settings)
            result = job.run(input_cap=args.budget).to_dict(include_content=args.show_content)
            result.update(
                mode="offline_probe" if args.command == "probe" else "offline_inspection",
                synthetic_input=job.synthetic,
                inference_calls=0,
            )
            if args.output is not None:
                save_inspection(args.output, result)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        counter = TiktokenCounter(settings.tokenizer)
        if args.command == "check":
            from rank_bm25 import BM25Plus

            BM25Plus([["setup"]]).get_scores(["setup"])
            counter.count_request(demo_request())
            print("deps ok")
            return 0
        if args.command == "demo-layers":
            from .demo import layer_demo

            print(json.dumps(layer_demo(counter), indent=2, ensure_ascii=False))
            return 0
        plan = plan_budget(required_request=demo_request(), config=settings.budget, counter=counter)
        print(json.dumps({"valid_request": plan.to_dict()}, indent=2))
        # Synthetic, bounded fixture: enough tokens to exceed the allowance.
        if settings.budget.input_allowance > 10000:
            raise ContextEngineError("Demo accepts input allowances up to 10,000 tokens")
        try:
            plan_budget(
                required_request=demo_request("oversized pin " * settings.budget.input_allowance),
                config=settings.budget,
                counter=counter,
            )
        except RequiredContextTooLarge as error:
            print(json.dumps({"expected_failure": error.to_dict()}, indent=2))
            return 0
        raise ContextEngineError("Oversized demo fixture unexpectedly fit")
    except ContextEngineError as error:
        print(json.dumps(error.to_dict()), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
