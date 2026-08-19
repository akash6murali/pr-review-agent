import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

STRONG_MODEL = os.getenv("STRONG_MODEL", "claude-sonnet-4-6")
FAST_MODEL   = os.getenv("FAST_MODEL",   "claude-haiku-4-5-20251001")

ANTHROPIC_API_KEY    = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN         = os.environ["GITHUB_TOKEN"]
GITHUB_WEBHOOK_SECRET = os.environ["GITHUB_WEBHOOK_SECRET"]

MAX_DIFF_CHARS           = 80_000   # truncate very large PRs before sending to LLM
MAX_COMMENTS_PER_REVIEWER = 8       # cap per reviewer to avoid noise
