"""Launch the bundled recorded demo on Windows, macOS or Linux, without API keys."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MAX_UNPACKED_BYTES = 64 * 1024 * 1024
# One immutable bundle per persona. Priya's manifest stays where it was; each server replays exactly one persona.
MANIFESTS = {"priya": "demo/manifest.json", "caroline": "demo/caroline.manifest.json"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_files(directory: Path, files: dict[str, str]) -> None:
    for name, digest in files.items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or sha256(path) != digest:
            raise ValueError(f"Demo file missing or changed: {name}. Preserve/rename this cache and retry.")


def prepare_bundle(root: Path = ROOT, destination: Path | None = None, persona: str = "priya") -> tuple[dict, Path]:
    manifest = json.loads((root / MANIFESTS[persona]).read_text(encoding="utf-8"))
    for value in (manifest["archive"], manifest["bundle_id"]):
        if PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts or "\\" in value or ":" in value:
            raise ValueError("Unsafe path in demo manifest")
    if PurePosixPath(manifest["bundle_id"]).name != manifest["bundle_id"]:
        raise ValueError("Unsafe bundle identifier")
    archive = root / "demo" / manifest["archive"]
    if sha256(archive) != manifest["archive_sha256"]:
        raise ValueError("Demo archive checksum mismatch; pull a complete copy of the repository.")
    files = manifest["files"]
    for name in files:
        if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name or ":" in name:
            raise ValueError("Unsafe path in demo manifest")
    destination = destination or root / ".demo-data" / manifest["bundle_id"]
    if destination.exists():
        verify_files(destination, files)
        return manifest, destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(files) or set(names) != set(files):
            raise ValueError("Demo archive contents do not match its manifest")
        if sum(item.file_size for item in bundle.infolist()) > MAX_UNPACKED_BYTES:
            raise ValueError("Demo archive is larger than the supported bundle size")
        temporary = Path(tempfile.mkdtemp(prefix=destination.name + ".partial-", dir=destination.parent))
        for name in names:
            data = bundle.read(name)
            if hashlib.sha256(data).hexdigest() != files[name]:
                raise ValueError(f"Demo archive contains a changed file: {name}")
            path = temporary / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    verify_files(temporary, files)
    temporary.rename(destination)
    return manifest, destination


def replay_environment(root: Path, data: Path, *, api_only: bool = False, persona: str = "priya") -> dict[str, str]:
    env = dict(os.environ)
    env.update(APP_MODE="historical", LLM_MODE="replay", REPLAY_ONLY="1", PUBLIC_DEMO="1", DEMO_PERSONA=persona,
               RECORDED_RUN=str(data / "recording.sqlite"), SNAPSHOT_DIR=str(data / "snapshot"),
               STATE_DB=str(root / ".demo-runtime/state.sqlite"), RUNS_DIR=str(root / ".demo-runtime/runs"),
               STATIC_DIR=str(root / ".demo-runtime/no-static" if api_only else root / "frontend/dist"),
               PYTHONIOENCODING="utf-8")
    # Explicit empty values take precedence over .env, without modifying or sharing anyone's file.
    for key in ("GEMINI_API_KEY", "GEMINI_API_KEY_BACKUPS", "EODHD_API_KEY", "FINNHUB_API_KEY",
                "ALPACA_KEY_ID", "ALPACA_SECRET_KEY", "DEMO_PASSCODE", "TASK_SECRET"):
        env[key] = ""
    return env


def venv_python(root: Path) -> Path:
    return root / "backend/.venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def setup(root: Path, *, api_only: bool) -> None:
    python = venv_python(root)
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(root / "backend/.venv")], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "-e", ".[dev]"], cwd=root / "backend", check=True)
    if not api_only:
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            raise ValueError("Install Node.js 20+ (including npm), then retry --setup")
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=root / "frontend", check=True)
        subprocess.run([npm, "run", "build"], cwd=root / "frontend", env={**os.environ, "VITE_MOCK": "0"}, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", action="store_true", help="Install dependencies and build the UI first")
    parser.add_argument("--check", action="store_true", help="Verify/extract bundle without dependencies, API keys or server")
    parser.add_argument("--api-only", action="store_true", help="Serve API for frontend development with VITE_MOCK=0")
    parser.add_argument("--persona", choices=sorted(MANIFESTS), default="priya",
                        help="Which recorded demo to replay (default: priya, the balanced demo)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    if sys.version_info < (3, 11):  # noqa: UP036 - launcher must explain prerequisites before creating a venv
        parser.error("Python 3.11+ is required")
    try:
        manifest, data = prepare_bundle(persona=args.persona)
        with sqlite3.connect(f"{(data / 'recording.sqlite').resolve().as_uri()}?mode=ro", uri=True) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Recorded SQLite integrity check failed")
        print(f"Verified {manifest['bundle_id']}: {manifest['days']} trading days, {manifest['agent_runs']} saved investigations.", flush=True)
        if args.check:
            return 0
        if args.setup:
            setup(ROOT, api_only=args.api_only)
        python = venv_python(ROOT)
        if not python.exists() or (not args.api_only and not (ROOT / "frontend/dist/index.html").exists()):
            raise ValueError("First run: python scripts/demo.py --setup")
        (ROOT / ".demo-runtime").mkdir(exist_ok=True)
        print(f"Recorded demo: http://{args.host}:{args.port}/ — choose Demo. Ctrl+C stops this server.", flush=True)
        print("No API keys/provider calls. Live questionnaire works; new Live investigations are disabled.", flush=True)
        return subprocess.run([str(python), "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", str(args.port)],
                              cwd=ROOT / "backend", env=replay_environment(ROOT, data, api_only=args.api_only, persona=args.persona), check=False).returncode
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print(f"Demo startup: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
