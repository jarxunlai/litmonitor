# LitMonitor

LitMonitor is a personal biomedical literature monitor for researchers. It supports manual PubMed search, saved weekly search profiles, SQLite persistence, deduplication, rule-based relevance scoring, optional LLM analysis, digest emails, a Typer CLI, and a small FastAPI/Jinja2 Web UI.

The MVP is a local single-user tool. If you expose it through Cloudflare Tunnel, protect it with Cloudflare Access, Zero Trust, email login, or another access-control layer.

## Install

Install Pixi first: <https://pixi.sh/latest/>

```bash
pixi install
cp .env.example .env
pixi run init-db
```

Common commands:

```bash
pixi run lit search "pulmonary hypertension endothelial single-cell" --since 30d
pixi run web
pixi run web-prod
pixi run test
pixi run lit profile run "PH endothelial weekly" --use-llm --send-email
```

The Web app listens on:

```text
http://127.0.0.1:8000
```

Important: `127.0.0.1` is local to the machine running LitMonitor. If LitMonitor is running on a remote server, opening `http://127.0.0.1:8000` in your laptop browser points to your laptop, not the server. Use one of these access paths:

- VS Code / SSH port forwarding from remote `8000` to local `8000`
- SSH tunnel: `ssh -L 8000:127.0.0.1:8000 user@server`
- Cloudflare Tunnel, for example `litmonitor.example.com -> http://127.0.0.1:8000`

Health check:

```bash
curl http://127.0.0.1:8000/health
```

If your shell has an HTTP proxy configured and local health checks fail, bypass the proxy:

```bash
curl --noproxy '*' http://127.0.0.1:8000/health
```

## Configuration

Secrets must live in `.env` or server environment variables. Do not commit `.env`, SMTP passwords, NCBI API keys, LLM API keys, Cloudflare tunnel credentials JSON, `deploy/cloudflare/config.yml`, local database files, or logs.

Key settings:

```env
DATABASE_URL=sqlite:///./data/litmonitor.db
NCBI_API_KEY=
APP_HOST=127.0.0.1
APP_PORT=8000
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

## CLI

Initialize the database:

```bash
pixi run lit init-db
```

Manual search:

```bash
pixi run lit search "pulmonary hypertension endothelial single-cell" --journal "Nature Medicine" --journal "Circulation" --since 30d
```

Create a weekly profile:

```bash
pixi run lit profile add \
  --name "PH endothelial weekly" \
  --include "pulmonary hypertension" \
  --include "endothelial" \
  --include "single-cell" \
  --exclude "case report" \
  --exclude "editorial" \
  --journal "Nature Medicine" \
  --journal "Circulation" \
  --journal "American Journal of Respiratory and Critical Care Medicine" \
  --schedule weekly \
  --email your@email.com
```

Run profiles:

```bash
pixi run lit profile list
pixi run lit profile run "PH endothelial weekly"
pixi run lit profile run "PH endothelial weekly" --send-email
pixi run lit profile run "PH endothelial weekly" --use-llm --send-email
```

Analyze one saved paper:

```bash
pixi run lit analyze-paper --pmid 12345678
pixi run lit analyze-paper --paper-id 1 --profile "PH endothelial weekly"
pixi run lit analyze-paper --paper-id 1 --llm-backend openai-compatible
pixi run lit analyze-paper --paper-id 1 --llm-backend cli
```

Digest and export:

```bash
pixi run lit digest preview --profile "PH endothelial weekly"
pixi run lit digest send --profile "PH endothelial weekly"
pixi run lit export --profile "PH endothelial weekly" --format csv
pixi run lit export --profile "PH endothelial weekly" --format bibtex
```

Standalone paper reports:

```bash
pixi run lit paper digest --pmid 42020743 --topic-keyword single-cell --topic-keyword lung
pixi run lit paper digest --doi 10.1038/s41586-026-10399-6 --output-format json
pixi run lit paper digest --paper-id 1 --output-dir data/reports/paper-digests/example
```

High-impact weekly reports:

```bash
pixi run lit report weekly-big \
  --date-from 2026-04-19 \
  --date-to 2026-04-26 \
  --interest-keyword single-cell \
  --interest-keyword spatial \
  --interest-keyword pulmonary
```

These commands embed the useful behavior from the Bioinfor-Claw `paper-digest-single`
and `big-papers-weekly-report` modules into LitMonitor. Outputs are written under
`data/reports/...` by default and include a `manifest.json` plus structured
`json`, `tsv`, and `md` files for downstream Web/API use.

Set `DIGEST_MAX_PAPERS_PER_RUN=20` to cap each emailed digest at 20 papers.

## LLM Backends

LLM analysis is optional. If an LLM call fails, LitMonitor records the failure and continues search, database writes, digest generation, and email delivery.

DeepSeek:

```env
LLM_ENABLED=true
LLM_BACKEND=openai-compatible
LLM_API_BASE=https://api.deepseek.com
LLM_API_KEY=your_deepseek_key
LLM_MODEL=deepseek-v4-pro
LLM_THINKING_TYPE=enabled
LLM_REASONING_EFFORT=high
LLM_STREAM=false
LLM_FORCE_JSON_MODE=false
```

GLM / Zhipu:

```env
LLM_ENABLED=true
LLM_BACKEND=openai-compatible
LLM_API_BASE=https://api.z.ai/api/paas/v4
LLM_API_KEY=your_glm_key
LLM_MODEL=glm-5.1
LLM_TEMPERATURE=1.0
LLM_MAX_TOKENS=4096
LLM_THINKING_TYPE=enabled
LLM_REASONING_EFFORT=
LLM_STREAM=false
LLM_FORCE_JSON_MODE=false
LLM_RETRY_ATTEMPTS=3
LLM_RETRY_BACKOFF_SECONDS=30
LLM_FALLBACK_BACKEND=cli
```

OpenAI-compatible:

```env
LLM_ENABLED=true
LLM_BACKEND=openai-compatible
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=your_openai_key
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=0
LLM_THINKING_TYPE=
LLM_REASONING_EFFORT=
LLM_STREAM=false
LLM_FORCE_JSON_MODE=true
LLM_RETRY_ATTEMPTS=3
LLM_RETRY_BACKOFF_SECONDS=10
LLM_FALLBACK_BACKEND=
```

Local CLI backend:

```env
LLM_ENABLED=true
LLM_BACKEND=cli
LLM_CLI_COMMAND=codex
LLM_CLI_ARGS=exec --json
LLM_CLI_TIMEOUT_SECONDS=120
```

The CLI backend requires the command to be available in the service shell. It sends the prompt to stdin and expects stdout to contain JSON. If the local CLI tool is unavailable or returns invalid JSON, LitMonitor skips that analysis and keeps the rest of the run moving.

Set `LLM_FALLBACK_BACKEND=cli` to use the local CLI backend when the primary OpenAI-compatible provider is rate-limited or otherwise unavailable.

## SMTP Email

Set these in `.env`:

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your_user
SMTP_PASSWORD=your_password
SMTP_FROM=litmonitor@example.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

For QQ Mail, use the full QQ email address as `SMTP_USER`, the generated SMTP authorization code as `SMTP_PASSWORD`, and prefer SSL on port 465:

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=your@qq.com
SMTP_PASSWORD=your_smtp_authorization_code
SMTP_FROM=your@qq.com
SMTP_USE_TLS=false
SMTP_USE_SSL=true
```

## Web And API

Start development server:

```bash
pixi run web
```

Production-style local server:

```bash
pixi run web-prod
```

Core API routes:

```text
GET  /health
GET  /api/v1/papers
POST /api/v1/papers/search
GET  /api/v1/profiles
POST /api/v1/profiles
POST /api/v1/profiles/{profile_id}/run
POST /api/v1/llm/analyze-paper/{paper_id}
POST /api/v1/digests/preview
POST /api/v1/digests/send
```

## Cloudflare Tunnel

Recommended mapping:

```text
litmonitor.example.com -> http://127.0.0.1:8000
```

Template config is in `deploy/cloudflare/config.example.yml`. Copy it to `deploy/cloudflare/config.yml` on the server and replace placeholders. Do not commit the real config or credentials JSON.

Typical tunnel setup:

```bash
cloudflared tunnel login
cloudflared tunnel create litmonitor
cloudflared tunnel route dns litmonitor litmonitor.example.com
cloudflared tunnel run litmonitor
```

If you already have a tunnel, make sure ingress points to:

```text
http://127.0.0.1:8000
```

Security note: do not expose the unauthenticated management UI directly to the public Internet. Use Cloudflare Access or another access-control layer.

## systemd

Templates:

```text
deploy/systemd/litmonitor.service.example
deploy/systemd/cloudflared-litmonitor.service.example
```

Copy them into `/etc/systemd/system/`, replace `<PROJECT_DIR>`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now litmonitor
sudo systemctl enable --now cloudflared-litmonitor
```

## Git

Initialize:

```bash
git init
git add .
git commit -m "chore: initialize litmonitor project"
```

Recommended branches:

```text
main       stable runnable version
dev        daily development
feature/*  feature work
fix/*      bug fixes
```

Use Conventional Commits:

```text
feat: add PubMed search service
fix: correct DOI deduplication
docs: add Cloudflare deployment guide
test: add LLM JSON parser tests
refactor: simplify digest builder
chore: update pixi tasks
deploy: add systemd templates
style: format code
```

Suggested milestones:

```text
Commit 1: skeleton, pixi, pyproject, README, env, gitignore
Commit 2: database models and init-db
Commit 3: PubMed query builder and search service
Commit 4: dedup and relevance scoring
Commit 5: CLI commands
Commit 6: FastAPI API and Web pages
Commit 7: LLM backend architecture
Commit 8: email digest and SMTP
Commit 9: APScheduler jobs
Commit 10: Cloudflare and systemd templates
Commit 11: tests and docs
```

## Tests

```bash
pixi run test
```

Tests mock external systems. They should not call PubMed, DeepSeek, GLM, OpenAI, Codex, or SMTP for real.

## Current Limits

- PubMed is the only implemented literature source.
- Web UI is intentionally simple and unauthenticated.
- Scheduler is in-process APScheduler, suitable for MVP use.
- PostgreSQL is available only through `DATABASE_URL`; no migration system is included yet.
- LLM JSON repair is conservative and only extracts the first balanced JSON object.

## Roadmap

- Add Crossref, Europe PMC, Semantic Scholar, and arXiv sources.
- Add authentication or integrate a reverse-proxy auth header.
- Add migrations with Alembic.
- Add richer digest filtering and per-profile journal weights.
- Add optional embedding-based ranking.
