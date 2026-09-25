import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("inventory", ROOT / "scripts/release_inventory.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_metadata_never_claims_release_or_license_approval(tmp_path):
    (tmp_path / "test.whl").write_bytes(b"synthetic-not-a-real-wheel")
    result = module.inventory(tmp_path)
    assert result["artifacts"][0]["sha256"] == hashlib.sha256(
        b"synthetic-not-a-real-wheel"
    ).hexdigest()
    assert not result["release_approved"]
    assert result["license_review"] == result["vulnerability_review"] == "PENDING"
    assert all(set(d) == {"name", "version", "license_expression", "license_classifiers"}
               for d in result["distributions"])


def test_empty_build_rejected(tmp_path):
    with pytest.raises(ValueError):
        module.inventory(tmp_path)


def test_output_not_overwritten(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("preserved")
    (tmp_path / "test.whl").write_bytes(b"test")
    monkeypatch.setattr("sys.argv", ["release_inventory.py", "--artifacts", str(tmp_path),
                                    "--output", str(output)])
    with pytest.raises(FileExistsError):
        module.main()
    assert output.read_text() == "preserved"
