"""LangGraph nodes: parallel reviewers + critic."""

from __future__ import annotations
import json
import asyncio
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .config import STRONG_MODEL, FAST_MODEL, MAX_COMMENTS_PER_REVIEWER
from .state import AgentState, ReviewComment

# ── Pydantic schemas for structured output ─────────────────────────────────────

class ReviewIssue(BaseModel):
    path: str = Field(description="File path relative to repo root, e.g. app/main.py")
    line: int = Field(description="Line number in the NEW version of the file")
    body: str = Field(description="Concise review comment — state the problem and suggest a fix")
    severity: Literal["critical", "high", "medium", "low"]

class ReviewFindings(BaseModel):
    issues: list[ReviewIssue]

class ConsolidatedReview(BaseModel):
    comments: list[ReviewIssue]
    summary: str = Field(description="2-4 sentence PR summary covering overall quality and top concerns")

# ── Reviewer prompts ───────────────────────────────────────────────────────────

REVIEWER_PROMPTS: dict[str, str] = {
    "security": """You are a Python security code reviewer. Analyze the diff for:
- Hardcoded secrets, tokens, or passwords
- SQL/command/path injection vulnerabilities
- Use of unsafe functions: eval(), exec(), pickle.loads(), subprocess with shell=True
- Missing input validation at API boundaries
- Broken authentication or authorization logic
- Insecure deserialization or file handling

Only flag real issues — avoid false positives. Skip issues in test files unless critical.""",

    "performance": """You are a Python performance code reviewer. Analyze the diff for:
- Database queries inside loops (N+1 pattern)
- Missing use of list comprehensions vs inefficient for-loops
- Repeated expensive computations that should be cached
- Large in-memory data structures that could be streamed
- Unnecessary object copies or conversions
- Missing indexes hinted by query patterns

Only flag clear, demonstrable performance problems with real impact.""",

    "logic": """You are a Python bug-finding code reviewer. Analyze the diff for:
- Off-by-one errors in loops or slicing
- Missing None/null checks before attribute access
- Bare except clauses that swallow errors silently
- Resource leaks — files or connections opened without context managers
- Race conditions in async or threaded code
- Incorrect boolean operator precedence
- Unreachable code or incorrect return paths

Be precise — only flag definite bugs or high-probability edge case failures.""",

    "style": """You are a Python code quality reviewer. Analyze the diff for:
- Missing type hints on public functions and methods
- Functions longer than ~50 lines that should be decomposed
- Magic numbers or strings that should be named constants
- Mutable default arguments (def f(x=[]): ...)
- Missing docstrings on public API functions/classes
- Dead code: unused imports, variables, or unreachable branches
- Naming that doesn't follow PEP 8 conventions

Focus on changes that materially affect readability or maintainability.""",
}

# ── LLM factory ───────────────────────────────────────────────────────────────

def _fast_llm() -> ChatAnthropic:
    return ChatAnthropic(model=FAST_MODEL, temperature=0)

def _strong_llm() -> ChatAnthropic:
    return ChatAnthropic(model=STRONG_MODEL, temperature=0)

# ── Individual reviewer ────────────────────────────────────────────────────────

async def _run_single_reviewer(reviewer_type: str, diff: str) -> list[ReviewComment]:
    llm = _fast_llm().with_structured_output(ReviewFindings)
    system = REVIEWER_PROMPTS[reviewer_type]
    human = (
        f"Review the following Python diff. Return up to {MAX_COMMENTS_PER_REVIEWER} issues.\n\n"
        f"DIFF:\n{diff}"
    )
    result: ReviewFindings = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=human),
    ])
    return [
        ReviewComment(
            path=issue.path,
            line=issue.line,
            body=f"**[{issue.severity.upper()}]** {issue.body}",
            severity=issue.severity,
            category=reviewer_type,
        )
        for issue in result.issues
    ]

# ── LangGraph nodes ────────────────────────────────────────────────────────────

async def run_reviewer(state: AgentState) -> dict:
    """Called in parallel (via Send()) for each reviewer type."""
    reviewer_type: str = state["reviewer_type"]  # injected by Send()
    findings = await _run_single_reviewer(reviewer_type, state["diff"])
    # Wrap in a list so operator.add merges them: [[...], [...], [...], [...]]
    return {"reviewer_findings": [findings]}


async def critique(state: AgentState) -> dict:
    """Consolidate all reviewer findings, dedupe, and write a PR summary."""
    all_findings: list[ReviewComment] = [
        comment
        for reviewer_list in state["reviewer_findings"]
        for comment in reviewer_list
    ]

    if not all_findings:
        return {
            "consolidated_comments": [],
            "summary": "No significant issues found in this PR.",
        }

    findings_json = json.dumps(all_findings, indent=2)
    llm = _strong_llm().with_structured_output(ConsolidatedReview)

    result: ConsolidatedReview = await llm.ainvoke([
        SystemMessage(content=(
            "You are a senior Python engineer conducting a final PR review. "
            "You receive findings from four specialist reviewers. Your job is to:\n"
            "1. Remove duplicate findings (same issue reported by multiple reviewers)\n"
            "2. Remove false positives or low-signal noise\n"
            "3. Prioritize: surface critical/high issues first\n"
            "4. Write a concise PR summary covering overall quality and the top 2-3 concerns\n"
            "Return at most 15 consolidated comments."
        )),
        HumanMessage(content=f"Reviewer findings:\n{findings_json}"),
    ])

    consolidated = [
        ReviewComment(
            path=c.path,
            line=c.line,
            body=c.body,
            severity=c.severity,
            category="consolidated",
        )
        for c in result.comments
    ]

    return {"consolidated_comments": consolidated, "summary": result.summary}
