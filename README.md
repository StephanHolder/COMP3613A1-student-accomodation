# comp3613a1

COMP 3613 Assignment 1 starter ([uwidcit/comp3613a1](https://github.com/uwidcit/comp3613a1)). Built on **FastStarter** (FastAPI + SQLModel).

**Assignment brief, agents, and GitHub Education link:** [ASSIGNMENT.md](ASSIGNMENT.md)

Based on the [fullstack FastAPI template](https://github.com/fastapi/full-stack-fastapi-template) with a layered architecture that reduces repeated code [(DRY)](https://en.wikipedia.org/wiki/Don%27t_repeat_yourself) across CLI, headless API, and fullstack UI.

This codebase follows an API-first, modern AJAX flow:

1. If the backend should render the UI, implement **views** that return the interface.
2. A small JavaScript helper (`app.js` / related static scripts) can intercept form submissions and call **API** endpoints instead.

Advantages of this structure:

1. Implement API endpoints first; views can stay thin
2. Reuse the same API for mobile / desktop clients
3. Pair with a separate frontend (Vue, React, Next, Nuxt, etc.)
4. Export endpoints for other services (including AI agents)
5. Drive features from the CLI when needed

---

## Initial setup

You need **Python 3.10+** and a **Java JRE** (`java` on `PATH`) for use-case PNGs. Coursework agents (Cursor, Copilot, or OpenCode) are in [ASSIGNMENT.md](ASSIGNMENT.md). **Node.js** is optional: only for rendering Mermaid model diagrams inside the PDF.

All project commands are a **Python CLI** (`manage.py`). There are no shell setup scripts.

Third-party binaries that are not on PyPI are **committed** under `vendor/` (PlantUML JAR, DejaVu fonts). Python packages are pinned in `requirements.txt`. Mermaid CLI is pinned in `package-lock.json`. See [vendor/README.md](vendor/README.md).

### 1. Clone

```bash
git clone https://github.com/uwidcit/comp3613a1.git
cd comp3613a1
```

### 2. Virtual environment and install dependencies

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run commands from the project root so `python manage.py` can import `app/`. No Poetry.

Optional, only if you will export a PDF that contains a Mermaid model diagram:

```bash
npm ci
```

That installs the mermaid-cli version pinned in `package-lock.json` into `node_modules/` (not committed).

### 3. Create `.env`

**Windows:**

```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**

```bash
cp .env.example .env
```

Defaults use a local SQLite file (`database.db`). Change `SECRET_KEY` before any real deployment. Set `CONFIG_PASSWORD` to enable the ops console at `/config` (leave empty to keep it disabled). If `.env` is missing, the app falls back to `.env.example` automatically.

### 4. Initialise the database (Python CLI)

Creates tables (drops existing by default) **and seeds demo users**:

```bash
python manage.py init
```

To include the listing-workflow landlord demo account:

```bash
python manage.py init --with-landlord
```

This adds `landlord` / `landlordpass`; the default student and admin demo accounts are unchanged.

| Username | Password    | Role         |
|----------|-------------|--------------|
| `bob`    | `bobpass`   | regular_user |
| `admin`  | `adminpass` | admin        |

Flags:

```bash
python manage.py init --no-drop   # create/seed without dropping
python manage.py init --no-seed   # tables only (skip demo users)
python manage.py seed --with-landlord  # seed demo accounts plus landlord
```

Seeding skips usernames that already exist. Add more rows in `cmd_seed` in `app/cli.py`. `python manage.py seed` still works if you only want to (re)insert demo users.

```bash
python manage.py users
```

### 5. Run the project (Python CLI)

```bash
python manage.py run
```

Then open http://127.0.0.1:5000 for the public landing page (host/port from `.env` / settings; default port **5000**). Sign in from there.

```bash
python manage.py run --host 127.0.0.1 --port 5000
python manage.py run --no-reload
```

---

## CLI reference

Commands are implemented in `app/cli.py` (stdlib `argparse`) and invoked via `manage.py`.

| Command | Purpose |
|---------|---------|
| `python manage.py init` | Drop (default), create DB tables, and seed demo users |
| `python manage.py seed` | Insert demo users only (also part of `init`) |
| `python manage.py run` | Start Uvicorn (reload unless `ENV=production`) |
| `python manage.py users` | Print users in the DB |
| `python manage.py transcripts` | Optional: package agent-written `docs/transcripts/*.md` into INDEX + zip (no IDE scrape) |
| `python manage.py report --name "..." --id "..."` | **Submission package:** merge `docs/judge.md`, package `docs/transcripts/`, write `docs/report.pdf`. Guide must run student-judge and **pull chats into `docs/transcripts/`** first (Copilot/Cursor/OpenCode). Incomplete drafts allowed. Fails only if course skills were edited |

| `python manage.py usecase` | Render `docs/diagrams/use-case.json` to a UML use-case PNG via the vendored PlantUML JAR (`docs/diagrams/use-case.png`) |
| `python manage.py skills-verify` | Check course skills against `.agents/skills.lock.json` |
| `python manage.py --help` | Show all commands |

Typical reset-and-start:

```bash
# venv activated, cwd = project root
python manage.py init
python manage.py run
```

The app binds `0.0.0.0` and reads `PORT` when Render sets it. Locally it uses `APP_PORT` (default **5000**).

---

## Deploy (Render MCP)

**Phase 6** — only after Phase 5 polish (named workflows work locally and you have steered UI/workflow/model refinements). Deploy a **Postgres database** and the **web app** on Render’s free plan. Agents talk to Render through the [Render MCP server](https://render.com/docs/mcp-server) (`https://mcp.render.com/mcp`). This repo already ships the MCP config for each supported agent — do **not** paste an API key into a committed file. Do not put the **database** password in the report or the video. **App** usernames and passwords belong in `docs/report.md`.

| Agent | MCP config in this repo | Auth |
|-------|-------------------------|------|
| **Cursor** | [`.cursor/mcp.json`](.cursor/mcp.json) | Prefer `/add-plugin render` then **Authenticate** (OAuth). Or create an [API key](https://dashboard.render.com/u/settings?add-api-key) and put it only in your user `~/.cursor/mcp.json` headers — never in the repo. |
| **GitHub Copilot** (VS Code) | [`.vscode/mcp.json`](.vscode/mcp.json) | Create a Render [API key](https://dashboard.render.com/u/settings?add-api-key). Open `.vscode/mcp.json`, click **Start**, paste the key when prompted (`${input:render-api-key}`). Use Copilot Chat in **Agent** mode. See [Extend Copilot Chat with MCP](https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/extend-copilot-chat-with-mcp). |
| **OpenCode** | [`opencode.json`](opencode.json) | From the project root run `opencode`, then `/mcps` (or `opencode mcp auth render`) and finish OAuth in the browser. |

Service shape lives in [`render.yaml`](render.yaml) (Blueprint reference for the agent — create resources with MCP, do not also apply the Blueprint in the Dashboard).

1. Push your repo to GitHub (Render clones the remote; it cannot deploy an unpushed folder).
2. Create a free [Render](https://render.com) account. Connect MCP for your agent using the table above, then set the active workspace (e.g. “Set my Render workspace to …”).
3. Ask the agent to deploy using the Render MCP, matching `render.yaml`:
   - `create_postgres` — name `faststarter-db`, plan `free`, region `oregon`, disk 1 GB
   - `create_web_service` — runtime `python`, plan `free`, **same region**, repo and branch, build `pip install -r requirements.txt`
4. Set env vars on the web service (use the database **internal** connection string, not the external one):
   - `DATABASE_URI` — internal Postgres URL
   - `SECRET_KEY` — long random string
   - `ENV` — `production`
   - `PYTHON_VERSION` — `3.12.7`
5. Start command (do not drop tables on each boot):

```bash
python manage.py init --no-drop && python manage.py run --host 0.0.0.0 --port $PORT
```

6. Confirm the deploy is live and `GET /health` succeeds. Put the public URL and the marker logins (username, password, role) in `docs/report.md`.

Free web services sleep after inactivity. Free Postgres expires after 30 days. Do not also apply `render.yaml` in the Dashboard if the MCP already created these resources — that makes a second copy.

---

## Agents: Cursor, Copilot, or OpenCode

Pick **one** of these. All three load Guide and Judge from this repo. Web chatbots (chatgpt.com, claude.ai, gemini.google.com) do not.

Start every build session with:

```text
Use the student-build skill.

Phase 1. Assigned project: …
Workflows (at least three; format Feature (user); steps go in the wireframe):
- Explore/Search Publications (Public)
- …
- …
```

When finished: ask the Guide to **build the report**. That run writes `docs/judge.md`, pulls every Guide chat into `docs/transcripts/` (Copilot Agent, Cursor, or OpenCode — not a Cursor-only scrape), then `python manage.py report` packages them and builds the PDF.

### GitHub Education (student license)

Apply here (sign in, then **Start an application**):

**https://github.com/settings/education/benefits**

Docs: [Apply to GitHub Education as a student](https://docs.github.com/en/education/about-github-education/github-education-for-students/apply-to-github-education-as-a-student).

Use a verified **academic email** if your school issues one (UWI: `@my.uwi.edu`), plus proof of enrolment if asked. After approval, activate Copilot from that same benefits page — approval and Copilot activation are separate steps. Details: [Copilot for students](https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/enable-copilot/set-up-for-students).

If the student Copilot offer is not available yet, use **Copilot Free** in agent mode. Do not buy a paid plan for this course.

### Cursor (Hobby, no card)

1. Install [Cursor](https://cursor.com) and sign in. Stay on free **Hobby**.
2. **File → Open Folder** → this project root (not a parent folder).
3. New **Agent** chat. Confirm it can see `student-build` (or type `/student-build`).
4. Paste the Guide prompt above.
5. For Render deploy later: run `/add-plugin render` (or rely on [`.cursor/mcp.json`](.cursor/mcp.json)) and complete OAuth when asked. Docs: [Render MCP](https://render.com/docs/mcp-server).

### GitHub Copilot (agent mode)

Skills load only in **agent** mode or the Copilot CLI — not inline autocomplete.

1. Create a GitHub account if you do not have one.
2. Apply for [GitHub Education](https://github.com/settings/education/benefits) and activate Copilot (or use Copilot Free).
3. Install [VS Code](https://code.visualstudio.com/) and the **GitHub Copilot** and **GitHub Copilot Chat** extensions. Sign in with the same GitHub account.
4. **File → Open Folder** → this project root.
5. Open Copilot Chat and switch the mode to **Agent** (not Ask, not Edit).
6. Start with the prompt above. If the skill does not attach, say: `Use the student-build skill in .agents/skills/student-build/SKILL.md`.
7. For Render deploy later: open [`.vscode/mcp.json`](.vscode/mcp.json), click **Start**, paste a Render API key when prompted, then confirm tools appear in Copilot Chat (tools icon). Docs: [Extend Copilot Chat with MCP](https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/extend-copilot-chat-with-mcp) · [Render MCP](https://render.com/docs/mcp-server).

Optional CLI (same account): [Install GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli), then run it from this folder. It also reads `AGENTS.md` and `.github/copilot-instructions.md`.

One feature slice at a time — free quotas are limited.

### OpenCode

OpenCode is a free client. You still need a model (local, or a free API tier). Docs: [opencode.ai/docs](https://opencode.ai/docs/).

**Windows (PowerShell):**

```powershell
npm install -g opencode-ai
```

Or: `scoop install opencode` / `choco install opencode`. Desktop app: [opencode.ai/download](https://opencode.ai/download).

**macOS / Linux:**

```bash
curl -fsSL https://opencode.ai/install | bash
# or: brew install anomalyco/tap/opencode
# or: npm install -g opencode-ai
```

Then:

1. `cd` to this project root (the folder that contains `AGENTS.md`).
2. Run `opencode`.
3. Connect a model with `/connect` (or `opencode auth login`). Do **not** run `/init` — this repo already has `AGENTS.md`, and `/init` would overwrite it.
4. Start with the prompt above. OpenCode should follow `AGENTS.md` and can load `.agents/skills/student-build`.
5. For Render deploy later: [`opencode.json`](opencode.json) already lists the Render MCP — run `/mcps` and authenticate when prompted.

More setup detail: [`.agents/skills/README.md`](.agents/skills/README.md).

---

## Architecture

This starter uses a layered FastAPI layout (see `docs/diagrams/application-components.jpg`):

- **Routes** — HTTP entry; thin; call services; return HTML/JSON/redirects
- **Dependencies** — shared resources (`SessionDep`, auth)
- **Schemas** — validated request/response shapes
- **Services** — application rules; coordinate repositories; **no SQL**
- **Repositories** — persistence (CRUD / queries); **no business policy**
- **Models** — SQLModel tables; structure only

A route that runs `select(…)` / `db.exec(…)` breaks the architecture. Put filters and commits in repositories; put workflow rules in services.

## App structure

```text
comp3613a1
|-- .agents/skills/           # Guide + Judge (Cursor, Copilot, OpenCode)
|-- .cursor/skills/          # same skills (older Cursor)
|-- .cursor/mcp.json         # Render MCP (Cursor)
|-- .vscode/mcp.json         # Render MCP (Copilot / VS Code)
|-- opencode.json            # Render MCP (OpenCode)
|-- render.yaml              # Render Blueprint reference for MCP deploy
|-- .github/copilot-instructions.md
|-- AGENTS.md                # always-on: use Guide unless asked to Judge
|-- ASSIGNMENT.md            # course brief, agents, GitHub Education link
|-- README.md
|-- manage.py                # python manage.py init|seed|run|users
|-- .env.example
|-- env.example              # legacy alias of .env.example
|-- vendor/                  # PlantUML JAR + DejaVu fonts (committed)
|-- package.json             # pinned mermaid-cli
|-- package-lock.json
|-- requirements.txt          # pinned Python deps (pip install -r requirements.txt)
|-- pyproject.toml            # package metadata only (optional; not required for local run)
|-- app/
|    |- cli.py               # Python CLI: init / seed / run / users
|    |- main.py
|    |- database.py
|    |- models/
|    |- repositories/
|    |- routers/
|    |- schemas/
|    |- services/
|    |- static/
|    |- templates/
|    |- utilities/
```

> **Note:** Prefer a local `.env` (copy from `.env.example`). If `.env` is missing, settings load from `.env.example` (or legacy `env.example`). See `app/config.py`.

## Using this in production

1. Change default configuration (production database, secret, environment)
2. Review `config.py` for scalability settings
3. Add a migration tool such as Alembic
4. Consider Docker for deployment
5. Prefer secure cookie practices over casual localStorage token storage where appropriate
