import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("operations", ROOT / "scripts/operations_check.py")
operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operations)


def test_recovery_and_index_reuse_drill():
    report = operations.drill(turns=4, samples=2)
    assert all(report["checks"].values())
    assert not report["production_qualified"]
    assert report["inference_calls"] == 0
    assert report["index_work"] == {
        "cold_processed": 4, "unchanged_processed": 0, "restored_processed": 3,
    }
    assert report["milliseconds"]["assembly_p95"] >= report["milliseconds"]["assembly_p50"]


@pytest.mark.parametrize("kwargs", [{"turns": 1}, {"turns": True}, {"samples": 0},
                                   {"turns": 1001}, {"samples": 101}])
def test_bounded_workload(kwargs):
    with pytest.raises(ValueError):
        operations.drill(**kwargs)


def test_existing_output_refused_before_drill(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("preserved")
    monkeypatch.setattr("sys.argv", ["operations_check.py", "--output", str(output)])
    monkeypatch.setattr(operations, "drill", lambda **kwargs: pytest.fail("must not run"))
    with pytest.raises(SystemExit):
        operations.main()
    assert output.read_text() == "preserved"
