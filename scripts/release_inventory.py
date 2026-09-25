"""Local dependency metadata/build hashes, not a vulnerability or license approval."""

import argparse
import hashlib
import json
from importlib import metadata
from pathlib import Path


def inventory(artifacts):
    files = sorted(Path(artifacts).iterdir())
    files = [p for p in files if p.name.endswith((".whl", ".tar.gz"))]
    if not files or any(p.is_symlink() or not p.is_file() for p in files):
        raise ValueError("Expected regular built artifacts")
    dependencies = []
    for distribution in metadata.distributions():
        info = distribution.metadata
        dependencies.append({
            "name": info["Name"], "version": distribution.version,
            "license_expression": info.get("License-Expression"),
            "license_classifiers": [v for v in info.get_all("Classifier", [])
                                    if v.startswith("License ::")],
        })
    return {
        "status": "INVENTORY_ONLY", "release_approved": False,
        "license_review": "PENDING", "vulnerability_review": "PENDING",
        "scope": "Installed local build/test environment;not a runtime-only SBOM or attestation",
        "artifacts": [{"name": p.name, "bytes": p.stat().st_size,
                       "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
        "distributions": sorted(dependencies, key=lambda d: (d["name"].lower(), d["version"])),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = inventory(args.artifacts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": value["status"], "artifacts": len(value["artifacts"]),
                      "distributions": len(value["distributions"])}))


if __name__ == "__main__":
    main()
