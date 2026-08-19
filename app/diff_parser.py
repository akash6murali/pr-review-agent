"""Parse unified git diffs into structured per-file representations."""

from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class FileDiff:
    path: str
    raw_diff: str                  # the full diff block for this file
    valid_lines: set[int]          # line numbers that exist in the new file version


def parse_diff(diff_text: str) -> list[FileDiff]:
    """Split a multi-file unified diff into per-file FileDiff objects."""
    files: list[FileDiff] = []
    blocks = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)

    for block in blocks:
        if not block.strip():
            continue
        file_diff = _parse_file_block(block)
        if file_diff and file_diff.path.endswith(".py"):
            files.append(file_diff)

    return files


def _parse_file_block(block: str) -> FileDiff | None:
    path_match = re.search(r"^\+\+\+ b/(.+)$", block, re.MULTILINE)
    if not path_match:
        return None

    path = path_match.group(1)
    valid_lines: set[int] = set()
    new_line = 0

    for line in block.splitlines():
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk_match:
            new_line = int(hunk_match.group(1)) - 1
            continue

        if line.startswith("+++") or line.startswith("---") or line.startswith("diff") or line.startswith("index"):
            continue

        if line.startswith("+"):
            new_line += 1
            valid_lines.add(new_line)
        elif line.startswith("-"):
            pass  # deleted line — no new file line number
        else:
            new_line += 1
            valid_lines.add(new_line)  # context lines are also valid comment targets

    return FileDiff(path=path, raw_diff=block, valid_lines=valid_lines)


def format_diff_for_review(files: list[FileDiff], max_chars: int) -> str:
    """Produce a single annotated string to pass to reviewers, respecting a char budget."""
    parts: list[str] = []
    budget = max_chars

    for f in files:
        chunk = f"### FILE: {f.path}\n```diff\n{f.raw_diff}\n```\n"
        if len(chunk) > budget:
            chunk = chunk[:budget] + "\n... [truncated]"
            parts.append(chunk)
            break
        parts.append(chunk)
        budget -= len(chunk)

    return "\n".join(parts)
