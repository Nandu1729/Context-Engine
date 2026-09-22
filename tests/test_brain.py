"""Regression checks for the project-memory integrity boundary, not the engine."""

import importlib.util
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("brain", PROJECT / "scripts/brain.py")
brain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brain)


class BrainIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="context-brain-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        linked_artifacts = [
            PROJECT / name
            for name in (
                "examples/inspection-input.json",
                "output/c03-inspection.json",
                "output/c04-benchmark-check.json",
                "output/c04-resume.json",
                "output/c05-provider-demo.json",
                "output/c07-memory-demo.json",
                "output/c08-service-demo.json",
                "output/c06-live-batch-004.json",
                "output/c06-live-progress-report/leaderboard.md",
                "output/c06-live-report-021/leaderboard.md",
                "output/c06-live-report-042/leaderboard.md",
                "output/c06-live-report-061/leaderboard.md",
                "output/c06-live-report-068/leaderboard.md",
                "output/c06-live-report-100/leaderboard.md",
                "output/c06-live-report-131/leaderboard.md",
                "output/c06-live-report-138/leaderboard.md",
                "output/c06-live-report-144/leaderboard.md",
                "output/c06-live-report-146/leaderboard.md",
                "output/c06-live-report-171/leaderboard.md",
                "output/c06-live-report-177/leaderboard.md",
                "output/c06-live-report-223/leaderboard.md",
                "output/c06-report/leaderboard.md",
                "output/c06-report/context_cost.png",
                "output/c06-report/recall_by_zone.png",
            )
        ]
        linked_artifacts.extend((PROJECT / "src/context_engine/evaluation/data").glob("*.json"))
        for source in [*brain.documents(PROJECT), *linked_artifacts]:
            name = source.relative_to(PROJECT)
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        self.reindex()

    def reindex(self):
        with redirect_stdout(io.StringIO()):
            brain.write_index(self.root)

    def test_complete_project_passes(self):
        self.assertEqual(brain.check(self.root), [])

    def test_modified_source_is_rejected_without_parsing_crash(self):
        (self.root / "CONTEXT_ENGINEERING_PRD.md").write_text("changed", encoding="utf-8")
        self.assertTrue(any("hash changed" in error for error in brain.check(self.root)))

    def test_updated_memory_requires_index_refresh(self):
        path = self.root / "brain/STATE.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\nNew verified fact.\n", encoding="utf-8"
        )
        self.assertTrue(any("stale" in error for error in brain.check(self.root)))
        self.reindex()
        self.assertEqual(brain.check(self.root), [])

    def test_missing_requirement_mapping_is_rejected(self):
        path = self.root / "docs/REQUIREMENTS.md"
        content = path.read_text(encoding="utf-8")
        path.write_text(content.replace("| 23 | Token counting | C01 |\n", ""), encoding="utf-8")
        self.reindex()
        self.assertTrue(any("73 PRD sections" in error for error in brain.check(self.root)))

    def test_broken_link_is_rejected(self):
        path = self.root / "brain/INDEX.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n[missing](missing.md)\n", encoding="utf-8"
        )
        self.reindex()
        self.assertTrue(any("Broken/outside" in error for error in brain.check(self.root)))

    def test_unbounded_hot_memory_is_rejected(self):
        (self.root / "brain/STATE.md").write_text("memory " * 901, encoding="utf-8")
        self.reindex()
        self.assertTrue(any("900 words" in error for error in brain.check(self.root)))

    def test_search_is_bounded_and_does_not_follow_outside_symlink(self):
        with tempfile.TemporaryDirectory(prefix="context-brain-outside-") as outside:
            secret = Path(outside) / "outside.md"
            secret.write_text("# secretneedle\nprivate fixture only", encoding="utf-8")
            (self.root / "docs/outside.md").symlink_to(secret)
            self.assertEqual(brain.search(self.root, "secretneedle", 5, 20), [])
        hits = brain.search(self.root, "summary budget", 3, 20)
        self.assertTrue(hits)
        self.assertLessEqual(len(hits), 3)
        self.assertTrue(all(len(hit["excerpt"].split()) <= 20 for hit in hits))
        self.assertTrue(any(hit["path"] == "docs/ARCHITECTURE.md" for hit in hits))

    def test_resume_cap_rejects_instead_of_silently_truncating(self):
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(brain, "ROOT", self.root),
            patch("sys.argv", ["brain.py", "context", "--max-words", "1"]),
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            self.assertEqual(brain.main(), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("not been silently truncated", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
