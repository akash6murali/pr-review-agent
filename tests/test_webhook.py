import hashlib
import hmac
import json
import os

# Must set env vars BEFORE importing app — config.py reads them at import time
SECRET = "test-secret"
os.environ["GITHUB_WEBHOOK_SECRET"] = SECRET
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("GITHUB_TOKEN", "test")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_webhook_invalid_signature():
    body = b'{"action": "opened"}'
    r = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=bad", "X-GitHub-Event": "pull_request"},
    )
    assert r.status_code == 401


def test_webhook_ignores_non_pr_events():
    body = json.dumps({"action": "created"}).encode()
    r = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "X-GitHub-Event": "issue_comment"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"


def test_webhook_ignores_non_review_actions():
    payload = {
        "action": "closed",
        "pull_request": {"number": 1},
        "repository": {"full_name": "owner/repo"},
    }
    body = json.dumps(payload).encode()
    r = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "X-GitHub-Event": "pull_request"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"
