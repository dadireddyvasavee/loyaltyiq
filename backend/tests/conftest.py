import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["LLM_API_KEY"] = ""
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-0123456789"
os.environ["LLM_BASE_URL"] = "https://example.invalid/v1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


def register(client, org="Acme Café", email="owner@acme.io"):
    r = client.post("/api/auth/register", json={"organization_name": org, "full_name": "Owner", "email": email,
                                                "password": "secret123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def auth(client):
    return register(client)
