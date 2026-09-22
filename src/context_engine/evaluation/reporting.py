"""Deterministic scorecard, leaderboard and PNG figures from saved benchmark evidence only."""

import hashlib
import io
import json
from importlib import metadata
from pathlib import Path
from statistics import median

from ..errors import BenchmarkError
from .execution import validate_execution
from .grading import proportion
from .results import assess_targets, statistics


def scorecard(bundle, frozen, payload):
    manifest, records, validation = validate_execution(bundle, frozen, payload)
    receipt_by_id = {e["probe_id"]: e["receipt"] for e in payload["entries"] if e["receipt"]}
    groups = statistics(manifest, records)
    for group in groups:
        selected = [
            r
            for r in records
            if (r["model"], r["budget"], r["variant"])
            == (group["model"], group["budget"], group["variant"])
        ]
        receipts = [
            receipt_by_id[r["probe_id"]] for r in selected if r["probe_id"] in receipt_by_id
        ]
        costs = [r["result"]["new_cost_microusd"] for r in receipts]
        group["new_cost_microusd"] = sum(c for c in costs if c is not None)
        group["cost_complete"] = (
            bool(receipts) and all(c is not None for c in costs) and group["pending"] == 0
        )
        group["unknown_cost_outcomes"] = sum(c is None for c in costs)
        group["replays"] = sum(r["result"]["status"] == "replay" for r in receipts)
        group["median_estimated_input_tokens"] = (
            median(r["estimate"]["estimated_tokens"] for r in selected) if selected else None
        )
        group["median_estimated_input_reduction"] = (
            median(
                1 - r["estimate"]["estimated_tokens"] / r["raw_estimated_tokens"] for r in selected
            )
            if selected
            else None
        )
        attempts = [
            a
            for receipt in receipts
            for a in receipt["ledger_rows"]
            if a["id"] in receipt["result"]["attempt_ids"]
        ]
        usages = [json.loads(a["usage_json"]) for a in attempts if a["usage_json"]]
        group["observed_attempt_usage"] = {
            "input_tokens": sum(u["input_tokens"] for u in usages),
            "output_tokens": sum(u["output_tokens"] for u in usages),
            "cached_input_tokens_known": sum(u["cached_input_tokens"] or 0 for u in usages),
            "reasoning_tokens_known": sum(u["reasoning_tokens"] or 0 for u in usages),
            "cached_details_unknown": sum(u["cached_input_tokens"] is None for u in usages),
            "reasoning_details_unknown": sum(u["reasoning_tokens"] is None for u in usages),
            "attempts_with_usage": len(usages),
            "attempts": len(attempts),
            "unknown_usage_attempts": sum(a["cost"] is None for a in attempts),
        }
        group["zones"] = {}
        for zone in ("early", "middle", "late"):
            slots = [
                s
                for s in manifest.slots
                if (s["model"], s["budget"], s["variant"])
                == (group["model"], group["budget"], group["variant"])
                and bundle.fact(s["fact_id"])["zone"] == zone
            ]
            rows = [r for r in selected if bundle.fact(r["fact_id"])["zone"] == zone]
            group["zones"][zone] = {
                "retained": proportion(
                    sum(r["state"] != "non_fit" and r["retained_evidence"] for r in rows),
                    len(slots),
                ),
                "answer_correct": proportion(
                    sum(r["answer_correct"] is True for r in rows), len(slots)
                ),
                "completed": sum(r["state"] == "success" for r in rows),
            }
            if not any(r["state"] in ("success", "error", "truncated") for r in rows):
                group["zones"][zone]["answer_correct"] = {
                    "count": None,
                    "denominator": len(slots),
                    "rate": None,
                    "wilson95": None,
                }
    return {
        "schema_version": 1,
        "execution_id": payload["execution_id"],
        "snapshot_digest": payload["digest"],
        "mode": payload["profile"]["mode"],
        "validity": validation,
        "quality_acceptance": assess_targets(manifest, records, validation),
        "configuration": manifest.data,
        "provider_profile": payload["profile"],
        "groups": groups,
        "report_inference_calls": 0,
        "warning": "Synthetic UNKNOWN responses and prices; not model-quality or API-cost evidence"
        if payload["profile"]["mode"] == "offline"
        else (
            "Owner-confirmed free-tier pricing; zero configured charges are not a billing "
            "attestation or paid-plan savings measurement; replay is not an independent answer"
            if all(
                c["quota"].get("billing_mode") == "free_tier"
                for c in payload["profile"]["clients"].values()
            )
            else "Recorded usage and configured prices; replay is not an independent model answer"
        ),
    }


def leaderboard(card):
    lines = [
        "# Benchmark leaderboard",
        "",
        f"Validity: {card['validity']['status']}. Mode: {card['mode']}.",
        "",
        card["warning"],
        "",
        "Rows are in protocol order, not ranked across incompatible budgets or models.",
        "",
        "| Model | Budget | Variant | Fit | Retained | Correct / planned | Correct / completed "
        "| Pending / errors / truncated | New cost (micro-USD) |",
        "|---|---:|---|---|---|---|---|---|---:|",
    ]

    def count(value):
        numerator = value["count"] if value["count"] is not None else "unknown"
        return f"{numerator} / {value['denominator']}"

    for g in card["groups"]:
        lines.append(
            f"| {g['model']} | {g['budget']} | {g['variant']} | {count(g['fit_all_planned'])} | "
            f"{count(g['retained_fitting_all_planned'])} | "
            f"{count(g['answer_correct_all_planned'])} | {count(g['answer_correct_completed'])} | "
            f"{g['pending']} / {g['errors']} / {g['truncated']} | "
            f"{g['new_cost_microusd']}{'' if g['cost_complete'] else ' (known subtotal)'} |"
        )
    lines += [
        "",
        f"Quality acceptance: {card['quality_acceptance']['status']}.",
        "",
        "Retention requires fitting, source-backed evidence; it is not answer accuracy. "
        "Unknown usage remains unknown.",
        "Small correlated synthetic samples do not establish real-workload performance.",
        "",
    ]
    return "\n".join(lines)


def figures(card):
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except ImportError:
        raise BenchmarkError("PNG generation requires the reports extra") from None
    panels = list(dict.fromkeys((g["model"], g["budget"]) for g in card["groups"]))
    outputs = {}
    for kind in ("context_cost", "recall_by_zone"):
        fig = Figure(figsize=(12, 4 * len(panels)), layout="constrained")
        FigureCanvasAgg(fig)
        axes = fig.subplots(len(panels), 2, squeeze=False)
        for row_index, (model, budget) in enumerate(panels):
            groups = [g for g in card["groups"] if (g["model"], g["budget"]) == (model, budget)]
            labels = [g["variant"] for g in groups]
            left, right = axes[row_index]
            title = f"{model.rsplit('/', 1)[-1]} | budget {budget}"
            if kind == "context_cost":
                values = [g["median_estimated_input_tokens"] or 0 for g in groups]
                bars = left.bar(labels, values, color="#327e9e")
                left.axhline(budget, color="#a43e3e", linestyle="--", label="Input allowance")
                left.bar_label(
                    bars,
                    [
                        "N/A" if g["median_estimated_input_tokens"] is None else str(round(v))
                        for g, v in zip(groups, values, strict=True)
                    ],
                    fontsize=8,
                )
                left.set_ylabel("Median estimated input tokens")
                left.legend(fontsize=8)
                costs = [g["new_cost_microusd"] for g in groups]
                bars = right.bar(labels, costs, color="#86734b")
                right.bar_label(
                    bars,
                    [
                        str(c) + ("*" if not g["cost_complete"] else "")
                        for g, c in zip(groups, costs, strict=True)
                    ],
                    fontsize=8,
                )
                right.set_ylabel(
                    "Synthetic micro-USD"
                    if card["mode"] == "offline"
                    else "New estimated charge (micro-USD)"
                )
                right.set_title("New cost; * known subtotal, not full billing")
            else:
                for axis, metric in ((left, "retained"), (right, "answer_correct")):
                    for i, zone in enumerate(("early", "middle", "late")):
                        metrics = [g["zones"][zone][metric] for g in groups]
                        xs = [x + (i - 1) * 0.25 for x in range(len(groups))]
                        bars = axis.bar(
                            xs,
                            [m["rate"] or 0 for m in metrics],
                            width=0.24,
                            label=zone,
                            color=("#327e9e", "#bf8a45", "#6e9277")[i],
                        )
                        axis.bar_label(
                            bars,
                            [
                                f"{m['count']}/{m['denominator']}"
                                if m["denominator"] and m["count"] is not None
                                else "N/A"
                                for m in metrics
                            ],
                            fontsize=6,
                            rotation=90,
                            padding=3,
                        )
                    axis.set_xticks(range(len(labels)), labels)
                    axis.set_ylim(0, 1.25)
                    axis.set_yticks((0, 0.5, 1), ("0%", "50%", "100%"))
                    axis.legend(fontsize=8, loc="upper left")
                left.set_ylabel("Source-backed retained / planned")
                right.set_ylabel("Correct answers / planned")
                right.set_title(
                    "Synthetic answers only"
                    if card["mode"] == "offline"
                    else "Uncompleted answers remain in denominator"
                )
            left.set_title(title)
            for axis in (left, right):
                axis.spines[["top", "right"]].set_visible(False)
                axis.grid(axis="y", alpha=0.15)
                axis.set_axisbelow(True)
        fig.suptitle(
            f"{kind.replace('_', ' ').title()} — "
            f"{card['mode'].upper()} / {card['validity']['status']}\n"
            "Estimates and synthetic tests are not live-provider performance evidence",
            fontsize=13,
        )
        buffer = io.BytesIO()
        fig.savefig(
            buffer, format="png", dpi=130, metadata={"Software": "context-engine-report-v1"}
        )
        outputs[kind + ".png"] = buffer.getvalue()
    return outputs


def export_report(directory, card):
    outputs = {
        "scorecard.json": (
            json.dumps(card, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        ).encode(),
        "leaderboard.md": leaderboard(card).encode(),
        **figures(card),
    }
    for model in card["configuration"]["models"]:
        projection = {
            **card,
            "groups": [g for g in card["groups"] if g["model"] == model],
            "selected_model": model,
            "projection_note": "Model-specific scorecard; parent manifest retained",
        }
        outputs[model.rsplit("/", 1)[-1] + "-results.json"] = (
            json.dumps(projection, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode()
    manifest = {
        "execution_id": card["execution_id"],
        "snapshot_digest": card["snapshot_digest"],
        "report_inference_calls": 0,
        "matplotlib": metadata.version("matplotlib"),
        "pillow": metadata.version("pillow"),
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in outputs.items()},
    }
    outputs["report-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    try:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        for name, raw in outputs.items():
            with (directory / name).open("xb") as handle:
                handle.write(raw)
    except OSError:
        raise BenchmarkError(
            "Report destination must be a new writable directory; partial exports are not complete"
        ) from None
    return manifest
