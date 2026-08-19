from typing import Annotated, TypedDict
import operator


class ReviewComment(TypedDict):
    path: str
    line: int
    body: str
    severity: str   # critical | high | medium | low
    category: str   # security | performance | logic | style


class AgentState(TypedDict):
    pr_number: int
    repo_full_name: str
    diff: str
    # Annotated with operator.add so parallel Send() nodes can each append their list
    reviewer_findings: Annotated[list[list[ReviewComment]], operator.add]
    consolidated_comments: list[ReviewComment]
    summary: str
