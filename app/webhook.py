"""GitHub webhook handler with HMAC signature validation."""

from __future__ import annotations
import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.agent.config import MAX_DIFF_CHARS
from app.agent.graph import graph
from app.agent.state import AgentState
from app.diff_parser import parse_diff, format_diff_for_review
from app.github_client import get_pr_diff, post_review

log = logging.getLogger(__name__)
router = APIRouter()


def _verify_signature(body: bytes, signature: str) -> None:
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


async def _run_review(repo_full_name: str, pr_number: int) -> None:
    try:
        raw_diff = get_pr_diff(repo_full_name, pr_number)
        parsed_files = parse_diff(raw_diff)

        if not parsed_files:
            log.info("PR %s#%d has no Python changes — skipping", repo_full_name, pr_number)
            return

        diff_text = format_diff_for_review(parsed_files, MAX_DIFF_CHARS)
        valid_lines = {f.path: f.valid_lines for f in parsed_files}

        initial_state = AgentState(
            pr_number=pr_number,
            repo_full_name=repo_full_name,
            diff=diff_text,
            reviewer_type="",       # overwritten per Send() dispatch
            reviewer_findings=[],
            consolidated_comments=[],
            summary="",
        )

        result: AgentState = await graph.ainvoke(initial_state)

        post_review(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            comments=result["consolidated_comments"],
            summary=result["summary"],
            valid_lines_by_file=valid_lines,
        )
    except Exception:
        log.exception("Review failed for %s#%d", repo_full_name, pr_number)


@router.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
) -> dict:
    body = await request.body()
    _verify_signature(body, x_hub_signature_256)

    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}

    payload = await request.json()
    action = payload.get("action", "")
    if action not in {"opened", "synchronize", "reopened"}:
        return {"status": "ignored", "action": action}

    pr_number: int = payload["pull_request"]["number"]
    repo_full_name: str = payload["repository"]["full_name"]

    log.info("Queuing review for %s#%d (action=%s)", repo_full_name, pr_number, action)
    background_tasks.add_task(_run_review, repo_full_name, pr_number)

    return {"status": "processing", "pr": pr_number, "repo": repo_full_name}
