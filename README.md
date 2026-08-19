# PR Review Agent

An agentic GitHub PR reviewer powered by Claude. Installs as a webhook, runs four specialist AI reviewers in parallel on every PR, then a critic agent consolidates the findings and posts inline comments.

## Architecture

```
GitHub PR opened / updated
          │
          ▼  webhook (HMAC-validated)
   ┌─────────────────┐
   │   FastAPI app   │
   └────────┬────────┘
            │ fetch diff (GitHub API)
            ▼
   ┌─────────────────────────────────────────┐
   │           LangGraph Agent               │
   │                                         │
   │  ┌──────────┐  ┌──────────┐            │
   │  │ Security │  │   Perf   │  parallel  │
   │  │  Haiku   │  │  Haiku   │  fan-out   │
   │  └──────────┘  └──────────┘  via Send()│
   │  ┌──────────┐  ┌──────────┐            │
   │  │  Logic   │  │  Style   │            │
   │  │  Haiku   │  │  Haiku   │            │
   │  └──────────┘  └──────────┘            │
   │               │                        │
   │       ┌───────▼────────┐               │
   │       │  Critic        │  reflection   │
   │       │  Sonnet 4.6    │  + dedup      │
   │       └───────┬────────┘               │
   └───────────────┼─────────────────────────┘
                   │ post review (GitHub API)
                   ▼
          Inline comments + PR summary
```

**Patterns showcased:**
- **Parallel fan-out** — `Send()` in LangGraph dispatches all 4 reviewers concurrently
- **LLM-as-judge** — critic agent consolidates findings, removes false positives, assigns severity
- **Structured output** — Pydantic schemas enforce `{path, line, body, severity}` from every reviewer
- **Reflection** — critic does a second-pass over all findings before posting
- **Real webhook integration** — HMAC-SHA256 signature validation, GitHub review API

## Stack

| Component | Technology |
|---|---|
| Agent framework | LangGraph 1.x |
| Reviewers | Claude Haiku 4.5 (×4 parallel) |
| Critic | Claude Sonnet 4.6 |
| API server | FastAPI + uvicorn |
| GitHub integration | PyGithub |
| Hosting | Railway |
| CI/CD | GitHub Actions |

## Setup

### 1. Clone and install

```bash
git clone https://github.com/akash6murali/pr-review-agent
cd pr-review-agent
pip install -r requirements.txt
cp .env.example .env
# fill in ANTHROPIC_API_KEY, GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET
```

### 2. Configure the GitHub webhook

1. Go to your repo → **Settings → Webhooks → Add webhook**
2. **Payload URL**: `https://your-railway-url.up.railway.app/webhook`
3. **Content type**: `application/json`
4. **Secret**: a random string — copy it to `GITHUB_WEBHOOK_SECRET` in your `.env`
5. **Events**: select **Pull requests**

### 3. Deploy to Railway

```bash
railway login
railway init
railway up
```

Add environment variables in the Railway dashboard:
- `ANTHROPIC_API_KEY`
- `GITHUB_TOKEN`
- `GITHUB_WEBHOOK_SECRET`

### 4. Run locally

```bash
uvicorn app.main:app --reload
# expose via ngrok for local webhook testing:
ngrok http 8000
```

## CI/CD

- **CI** (`ci.yml`): runs `ruff` lint + `pytest` on every PR and push to `main`
- **CD** (`deploy.yml`): deploys to Railway on every push to `main`

Set `RAILWAY_TOKEN` in GitHub repo secrets (Settings → Secrets → Actions).

## Project Structure

```
pr-review-agent/
├── .github/workflows/
│   ├── ci.yml            # lint + test on every PR
│   └── deploy.yml        # deploy to Railway on main merge
├── app/
│   ├── main.py           # FastAPI app
│   ├── webhook.py        # webhook handler + signature validation
│   ├── github_client.py  # diff fetching + review posting
│   ├── diff_parser.py    # unified diff → structured FileDiff
│   └── agent/
│       ├── config.py     # env vars, model names, limits
│       ├── state.py      # AgentState + ReviewComment TypedDicts
│       ├── nodes.py      # reviewer + critic LangGraph nodes
│       └── graph.py      # LangGraph graph assembly
├── tests/
│   ├── test_diff_parser.py
│   └── test_webhook.py
├── Dockerfile
├── railway.toml
└── requirements.txt
```
