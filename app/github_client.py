"""GitHub API wrapper — fetch diffs and post review comments."""

from __future__ import annotations
import logging

from github import Github
from github.PullRequest import PullRequest

from app.agent.config import GITHUB_TOKEN
from app.agent.state import ReviewComment

log = logging.getLogger(__name__)

_gh = Github(GITHUB_TOKEN)


def get_pr_diff(repo_full_name: str, pr_number: int) -> str:
    repo = _gh.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)
    # PyGithub doesn't expose raw diff directly; use the requests session
    response = _gh._Github__requester.requestMemorizedHttpLib(  # type: ignore[attr-defined]
        "GET",
        pr.url,
        headers={"Accept": "application/vnd.github.v3.diff"},
        input=None,
        cnx=None,
    )
    if hasattr(response, "data"):
        raw = response.data
    else:
        raw = response[2]
    return raw.decode("utf-8") if isinstance(raw, bytes) else raw


def post_review(
    repo_full_name: str,
    pr_number: int,
    comments: list[ReviewComment],
    summary: str,
    valid_lines_by_file: dict[str, set[int]],
) -> None:
    repo = _gh.get_repo(repo_full_name)
    pr: PullRequest = repo.get_pull(pr_number)

    inline = []
    skipped = 0
    for c in comments:
        allowed = valid_lines_by_file.get(c["path"], set())
        if c["line"] in allowed:
            inline.append({
                "path": c["path"],
                "line": c["line"],
                "side": "RIGHT",
                "body": c["body"],
            })
        else:
            skipped += 1
            log.warning("Skipped comment on %s:%d — not in diff", c["path"], c["line"])

    if skipped:
        summary += f"\n\n> _{skipped} comment(s) omitted — referenced lines outside this diff._"

    pr.create_review(body=summary, event="COMMENT", comments=inline)
    log.info("Posted review on %s#%d — %d inline comment(s)", repo_full_name, pr_number, len(inline))
