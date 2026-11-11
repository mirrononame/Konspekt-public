import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
_TMP = Path(tempfile.mkdtemp(prefix="konspekt-test-"))
import fixture  # noqa: E402

DATA = fixture.make(_TMP)
os.environ["KONSPEKT_DATA"] = str(DATA)
os.environ["KONSPEKT_BETA"] = "1"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app import server
    with TestClient(server.app) as c:
        yield c


@pytest.fixture(scope="session")
def data_dir():
    return DATA
