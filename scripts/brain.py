#!/usr/bin/env python3
"""Offline, bounded project memory discovery. This is not the context runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
SOURCE_HASH = "1abb616cbd347aa8fea8064feb93af45727060acdb3e6a91708f4ee4ae39b43c"
REQUIRED = (
    "AGENTS.md",
    "README.md",
    "CONTEXT_ENGINEERING_PRD.md",
    "brain/INDEX.md",
    "brain/STATE.md",
    "brain/DECISIONS.md",
    "brain/JOURNAL.md",
    "brain/SUGGESTIONS.md",
    "docs/OWNER_REVIEW.md",
    "docs/CHECKPOINTS.md",
    "docs/REQUIREMENTS.md",
    "docs/ARCHITECTURE.md",
    "docs/EVALUATION.md",
    "docs/ENTERPRISE.md",
    "docs/SOURCES.md",
)


def documents(root: Path) -> list[Path]:
    candidates = list(root.glob("*.md"))
    for folder in ("brain", "docs"):
        candidates.extend((root / folder).rglob("*.md"))
    return sorted(
        p
        for p in candidates
        if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root.resolve())
    )


def headings(content: str) -> list[dict]:
    result = []
    fence = None
    for number, line in enumerate(content.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if fence is None and match:
            result.append({"line": number, "title": match.group(2)})
    return result


def make_index(root: Path) -> dict:
    entries = []
    for path in documents(root):
        raw = path.read_bytes()
        content = raw.decode("utf-8")
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "words": len(content.split()),
                "headings": headings(content),
            }
        )
    return {"schema_version": 1, "documents": entries}


def write_index(root: Path) -> int:
    target = root / "brain/index.json"
    if target.is_symlink():
        raise ValueError("Refusing to replace a symlinked brain index")
    payload = json.dumps(make_index(root), indent=2, ensure_ascii=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent, prefix=".brain-index-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f"Indexed {len(json.loads(payload)['documents'])} Markdown documents; no API calls.")
    return 0


def words(text: str) -> set[str]:
    return set(re.findall(r"[\w-]+", text.casefold()))


def search(root: Path, query: str, limit: int, excerpt_words: int) -> list[dict]:
    terms = words(query)
    if not terms:
        raise ValueError("Search requires at least one word")
    hits = []
    for path in documents(root):
        if "archive" in path.relative_to(root).parts:
            continue
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        sections = headings(content) or [{"line": 1, "title": path.stem}]
        for position, heading in enumerate(sections):
            start = heading["line"] - 1
            end = sections[position + 1]["line"] - 1 if position + 1 < len(sections) else len(lines)
            body_lines = lines[start:end]
            body = "\n".join(body_lines)
            matched = terms & words(body)
            if not matched:
                continue
            score = 4 * len(matched) + 2 * len(terms & words(heading["title"]))
            # Prefer curated project decisions over equally matching source text.
            if path.relative_to(root).parts[0] in ("brain", "docs"):
                score += 0.5
            # Start near the best matching line so large sections remain useful.
            best = max(
                range(len(body_lines)),
                key=lambda i: len(terms & words("\n".join(body_lines[i : i + 4]))),
            )
            excerpt = " ".join("\n".join(body_lines[best:]).split()[:excerpt_words])
            hits.append(
                {
                    "score": score,
                    "path": path.relative_to(root).as_posix(),
                    "line": start + best + 1,
                    "heading": heading["title"],
                    "excerpt": excerpt,
                }
            )
    return sorted(hits, key=lambda h: (-h["score"], h["path"], h["line"]))[:limit]


def check(root: Path) -> list[str]:
    errors = []
    for name in REQUIRED:
        path = root / name
        if (
            not path.is_file()
            or path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve())
        ):
            errors.append(f"Missing or unsafe required document: {name}")
    if errors:
        return errors

    source = (root / "CONTEXT_ENGINEERING_PRD.md").read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_HASH:
        errors.append("Original PRD hash changed; preserve source and record amendments separately")
        return errors
    source_text = source.decode("utf-8")
    source_sections = re.findall(r"^## (\d+)\.", source_text, re.MULTILINE)
    requirements = (root / "docs/REQUIREMENTS.md").read_text(encoding="utf-8")
    mapped = re.findall(r"^\| (\d+) \|", requirements, re.MULTILINE)
    if mapped != source_sections or mapped != [str(n) for n in range(1, 74)]:
        errors.append("Requirements must map all 73 PRD sections exactly once in order")
    checklist = source_text.split("## 69. Acceptance Criteria", 1)[1].split("## 70.", 1)[0]
    count = len(re.findall(r"^- \[ \]", checklist, re.MULTILINE))
    acceptance = re.findall(r"^\| V1-(\d+) \|", requirements, re.MULTILINE)
    if acceptance != [f"{n:02d}" for n in range(1, count + 1)]:
        errors.append("V1 traceability must match every original acceptance item exactly once")

    checkpoints = (root / "docs/CHECKPOINTS.md").read_text(encoding="utf-8")
    expected = [f"C{n:02d}" for n in range(13)]
    actual = re.findall(r"^## (C\d{2})\b", checkpoints, re.MULTILINE)
    rows = re.findall(
        r"^\| (C\d{2}) \|.*\| (PLANNED|ACTIVE|READY|ACCEPTED|BLOCKED) \|$",
        checkpoints,
        re.MULTILINE,
    )
    if actual != expected or [row[0] for row in rows] != expected:
        errors.append("Checkpoint headings/status table must define C00 through C12 exactly once")
    referenced = set(re.findall(r"\bC\d{2}\b", requirements + checkpoints))
    if referenced - set(expected):
        errors.append(f"Unknown checkpoint references: {sorted(referenced - set(expected))}")

    hot_words = sum(
        len((root / f"brain/{name}.md").read_text(encoding="utf-8").split())
        for name in ("INDEX", "STATE")
    )
    if hot_words > 900:
        errors.append(f"Hot memory exceeds 900 words: {hot_words}")
    if len((root / "brain/JOURNAL.md").read_text(encoding="utf-8").splitlines()) > 150:
        errors.append("Journal exceeds 150 lines; archive older evidence with a linked entry")

    for path in documents(root):
        content = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\]\((<[^>]+>|[^)]+)\)", content):
            target = match.group(1).strip("<>")
            if not target or target.startswith("#") or urlparse(target).scheme:
                continue
            target = unquote(target.split("#", 1)[0])
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                errors.append(f"Broken/outside local link: {path.relative_to(root)} -> {target}")

    index_path = root / "brain/index.json"
    try:
        if index_path.is_symlink():
            errors.append("Brain index must not be a symlink")
        elif json.loads(index_path.read_text(encoding="utf-8")) != make_index(root):
            errors.append("Brain index is stale; run: python3 scripts/brain.py index")
    except (OSError, ValueError):
        errors.append("Brain index missing/corrupt; run: python3 scripts/brain.py index")
    return errors


def bounded_integer(minimum: int, maximum: int):
    def parse(value: str) -> int:
        number = int(value)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"Value must be between {minimum} and {maximum}")
        return number

    return parse


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "index", "check"):
        commands.add_parser(command)
    context_parser = commands.add_parser("context")
    context_parser.add_argument("--max-words", type=bounded_integer(1, 8000), default=1600)
    search_parser = commands.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=bounded_integer(1, 10), default=5)
    search_parser.add_argument("--words", type=bounded_integer(1, 250), default=100)
    args = parser.parse_args()
    try:
        if args.command == "index":
            return write_index(ROOT)
        if args.command == "check":
            errors = check(ROOT)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}", file=sys.stderr)
                return 1
            hot = sum(
                len((ROOT / f"brain/{name}.md").read_text(encoding="utf-8").split())
                for name in ("INDEX", "STATE")
            )
            print(
                f"Brain checks passed: source hash, 73 sections, 27 V1 items, 13 checkpoints, "
                f"local links, current index; hot memory {hot}/900 words."
            )
        elif args.command == "status":
            print((ROOT / "brain/STATE.md").read_text(encoding="utf-8"))
        elif args.command == "context":
            content = "\n\n".join(
                (ROOT / name).read_text(encoding="utf-8")
                for name in ("AGENTS.md", "brain/INDEX.md", "brain/STATE.md")
            )
            if len(content.split()) > args.max_words:
                raise ValueError(
                    "Resume context exceeds word cap; compact hot memory or raise --max-words. "
                    "Required instructions have not been silently truncated."
                )
            print(content)
        elif args.command == "search":
            hits = search(ROOT, args.query, args.limit, args.words)
            if not hits:
                print("No matching project sections.")
            for hit in hits:
                print(f"{hit['path']}:{hit['line']} — {hit['heading']}\n{hit['excerpt']}\n")
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(f"Brain error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
