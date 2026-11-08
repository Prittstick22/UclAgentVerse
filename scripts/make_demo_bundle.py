"""Package a validated capture attempt into an immutable demo bundle (zip + manifest) for `scripts/demo.py`.

    python scripts/make_demo_bundle.py --persona caroline --attempt <attempt dir with READY.json> \
        --snapshot <the capture's inputs dir> --clearance "<Dev's exact permission text>"

Writes demo/assets/<bundle_id>.zip and demo/caroline.manifest.json. Refuses to overwrite either, to package an
attempt without READY.json, to include anything but the recording and the snapshot files, or to run without the
data owner's distribution clearance text (docs/DATA_SOURCES.md: clearance covers only the data it names).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = {"priya": "demo/manifest.json", "caroline": "demo/caroline.manifest.json"}
PROFILES = {"priya": "Priya, balanced", "caroline": "Caroline, aggressive"}
SECRET_MARKERS = (b"api_token=", b"apikey=", b"api_key=", b"GEMINI_API_KEY", b"EODHD_API_KEY", b"FINNHUB_API_KEY")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect(attempt: Path, snapshot: Path) -> dict[str, bytes]:
    files = {"recording.sqlite": (attempt / "recording.sqlite").read_bytes()}
    for item in sorted(snapshot.iterdir()):
        if item.is_file() and item.name != ".gitkeep":
            files["snapshot/" + item.name] = item.read_bytes()
    for name, data in files.items():
        if any(marker in data for marker in SECRET_MARKERS):
            raise ValueError(f"{name} looks like it contains a credential or request URL; not packaging")
    return files


def build(persona: str, attempt: Path, snapshot: Path, clearance: str, root: Path = ROOT) -> Path:
    ready = attempt / "READY.json"
    if not ready.is_file():
        raise ValueError("The attempt has no READY.json: only a complete, validated capture can be packaged")
    report = json.loads(ready.read_text(encoding="utf-8"))
    files = collect(attempt, snapshot)
    if sha256(files["recording.sqlite"]) != report["recording_sha256"]:
        raise ValueError("recording.sqlite does not match the hash in READY.json")
    bundle_id = f"{persona}-{report['start']}--{report['end']}-v1"
    archive = root / "demo/assets" / f"{bundle_id}.zip"
    manifest_path = root / MANIFESTS[persona]
    if archive.exists() or manifest_path.exists():
        raise ValueError("A bundle for this persona already exists; bundles are immutable (use a new version)")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as out:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))   # fixed time: same input, same archive
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, files[name])
    snapshot_manifest = json.loads(files["snapshot/manifest.json"].decode("utf-8")) if "snapshot/manifest.json" in files else {}
    manifest = {
        "format_version": 1, "bundle_id": bundle_id, "persona": persona,
        "archive": f"assets/{bundle_id}.zip", "archive_sha256": sha256(archive.read_bytes()),
        "files": {name: sha256(data) for name, data in sorted(files.items())},
        "start": report["start"], "end": report["end"], "days": report["days"], "agent_runs": report["agent_runs"],
        "model_calls": report.get("llm_calls"), "models": report.get("models"),
        "estimated_capture_usd": (report.get("estimated_campaign_spend") or {}).get("usd"),
        "capture_seconds": report.get("duration_s"), "recording_sha256": report["recording_sha256"],
        "snapshot_label": snapshot_manifest.get("label"),
        "fictional_profile": PROFILES[persona],
        "simulation": "paper trading; historical simulated results, not a forecast",
        "distribution_clearance": {"confirmed_by": "Dev (provider account owner)", "date": date.today().isoformat(),
                                   "scope": "Public distribution of the data and article text included in this bundle",
                                   "confirmation": clearance},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--persona", choices=sorted(MANIFESTS), required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--clearance", required=True, help="Dev's exact distribution-permission wording")
    args = parser.parse_args()
    try:
        print(f"Wrote {build(args.persona, args.attempt, args.snapshot, args.clearance)}")
    except (OSError, ValueError, KeyError) as error:
        print(f"Bundle not created: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
