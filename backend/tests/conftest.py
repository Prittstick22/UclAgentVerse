import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def snapshot_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("snapshot")
    subprocess.run([sys.executable, str(BACKEND / "scripts" / "make_synthetic_snapshot.py"), "--out", str(out)],
                   check=True, capture_output=True)
    return out


@pytest.fixture()
def state(snapshot_dir, monkeypatch):
    from app.container import build_state
    from app.settings import Settings

    s = Settings(snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="historical")
    return build_state(s, db_path=":memory:")
