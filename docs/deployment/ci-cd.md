# CI/CD & GitHub Actions

This project ships a set of GitHub Actions workflows under `.github/workflows/` that
cover the full delivery lifecycle: quality gates, security scanning, container builds,
documentation deployment, and automated dependency updates.

All workflows run on `ubuntu-latest`, use [`uv`](https://docs.astral.sh/uv/) for Python
tooling, and authenticate with the built-in `GITHUB_TOKEN` — **no extra secrets are
required** to get the security and CI pipelines running.

## Overview

| Workflow | File | Trigger | Purpose |
| -------- | ---- | ------- | ------- |
| **CI** | `ci.yml` | Push / PR to `main` | Lint, format, type check, tests + coverage |
| **CodeQL** | `codeql.yml` | Push / PR to `main`, weekly | Static analysis (SAST) for Python |
| **Secret Scan** | `gitleaks.yml` | Push / PR to `main`, weekly | Detect leaked secrets in git history |
| **Bandit** | `bandit.yml` | Push / PR to `main`, weekly | Python security linter |
| **Trivy** | `trivy.yml` | Push / PR to `main`, weekly | Vulnerability + IaC + image scan |
| **Dependency Audit** | `pip-audit.yml` | Dependency change, daily | CVE audit of locked dependencies |
| **Build & Push** | `docker.yml` | Push `main`/tags, PR | Test then build & push image to GHCR |
| **Deploy Docs** | `docs.yml` | Push `main` (docs), manual | Build MkDocs and deploy to GitHub Pages |
| **Dependabot** | `dependabot.yml` | Scheduled | Automated dependency update PRs |

!!! note "Repository setup"
    Some workflows publish results to GitHub's **Security** tab and require code
    scanning to be enabled. See [Repository setup](#repository-setup) at the bottom.

---

## CI & Quality

### `ci.yml` — Continuous Integration

**Purpose.** The main quality gate. Blocks merges when linting, formatting, or the test
suite fail, and produces a coverage report.

**Triggers.** Push and pull requests targeting `main`. Concurrent runs on the same ref
are cancelled to save minutes.

**How it works.** Two jobs run in parallel:

- **`lint`** — installs `uv`, then runs `ruff check` (lint) and `ruff format --check`
  (formatting). It also runs `mypy` for type checking. Because the codebase has not
  previously been type-checked in CI, `mypy` is marked `continue-on-error: true` so it
  reports findings without blocking. Flip this to `false` once the types are clean.
- **`test`** — a matrix over Python **3.11** and **3.12**. It spins up a
  `pgvector/pgvector:pg16` **service container**, enables the `vector` extension, and
  runs `pytest` with coverage (`pytest-cov`). The coverage XML is uploaded as an
  artifact.

**Dependencies.**

| Type | Item |
| ---- | ---- |
| Actions | `actions/checkout@v4`, `astral-sh/setup-uv@v4`, `actions/upload-artifact@v4` |
| Tools (via `uvx`) | `ruff`, `mypy`, `pytest-cov` |
| Service container | `pgvector/pgvector:pg16` |
| Secrets | None (placeholder API keys are injected as literals) |

**Configuration.**

- The `DATABASE_URL` env var points tests at the service container. Placeholder LLM keys
  (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GEMINI_API_KEY`) are set to
  `test-key` so config/import code does not fail — real keys are never needed for the
  unit suite.
- Add `[tool.ruff]` and `[tool.mypy]` sections to `pyproject.toml` to tune rules; the
  workflow picks them up automatically.
- Adjust the `matrix.python-version` list to change which interpreters are tested.

---

## Security

### `codeql.yml` — CodeQL (SAST)

**Purpose.** GitHub's first-party static analysis engine. Detects injection, unsafe
deserialization, path traversal, and other vulnerability classes in the Python code, and
publishes alerts to the Security tab.

**Triggers.** Push / PR to `main`, plus a weekly `cron` (Mondays) so newly published
queries run even without code changes.

**Dependencies.**

| Type | Item |
| ---- | ---- |
| Actions | `github/codeql-action/init@v3`, `github/codeql-action/analyze@v3` |
| Permissions | `security-events: write` |
| Repo setting | Code scanning enabled (see [Repository setup](#repository-setup)) |

**Configuration.** Analyzes `languages: python` with the `security-and-quality` query
suite. Swap to `security-extended` for more rules, or add a `paths-ignore` filter to
skip generated code.

### `gitleaks.yml` — Secret Scanning

**Purpose.** Highest-value scanner for this project. Because the repo carries a `.env`
file and integrates with Anthropic, OpenAI, and Google plus a `DATABASE_URL`, a
committed key is a real risk. gitleaks scans the **entire git history**, not just the
diff.

**Triggers.** Push / PR to `main`, plus a weekly `cron`.

**Dependencies.**

| Type | Item |
| ---- | ---- |
| Actions | `gitleaks/gitleaks-action@v2` |
| Checkout | `fetch-depth: 0` (full history required) |
| Secrets | `GITHUB_TOKEN` (auto). `GITLEAKS_LICENSE` **only** for GitHub Organizations |

**Configuration.** Add a `.gitleaks.toml` at the repo root to customize rules or
allowlist known false positives (for example the placeholder values in `.env.example`).

### `bandit.yml` — Python Security Lint

**Purpose.** Static security linter specialized for Python. Particularly relevant here
because of the crawler (`httpx`, `lxml` parsing untrusted HTML) and the FastAPI service.
Flags patterns like `eval`, unsafe XML parsing, `subprocess` misuse, and hardcoded
secrets.

**Triggers.** Push / PR to `main`, plus a weekly `cron`.

**Dependencies.**

| Type | Item |
| ---- | ---- |
| Actions | `astral-sh/setup-uv@v4` |
| Tools (via `uvx`) | `bandit` |

**Configuration.** Scans `src api scripts` (tests are excluded because `assert` is
expected there). The flags `-ll -ii` restrict output to **MEDIUM+ severity** and
**MEDIUM+ confidence** to keep signal high. Add a `[tool.bandit]` section in
`pyproject.toml` to skip specific checks.

### `trivy.yml` — Vulnerability & IaC Scan

**Purpose.** Broad supply-chain and infrastructure scanner. Two jobs:

- **`repo-scan`** — filesystem scan of the repository for vulnerable dependencies,
  misconfigurations, and leaked secrets.
- **`image-scan`** — builds the Docker image locally (no push) and scans the exact image
  that ships, including OS packages.

Both upload SARIF results to the Security tab.

**Triggers.** Push / PR to `main`, plus a weekly `cron`.

**Dependencies.**

| Type | Item |
| ---- | ---- |
| Actions | `aquasecurity/trivy-action@0.28.0`, `docker/setup-buildx-action@v3`, `docker/build-push-action@v6`, `github/codeql-action/upload-sarif@v3` |
| Permissions | `security-events: write` |
| Cache | GitHub Actions cache (`type=gha`) for the Docker build |
| Repo setting | Code scanning enabled (for SARIF upload) |

**Configuration.** Severity is limited to `CRITICAL,HIGH`; `ignore-unfixed: true` on the
image scan hides vulnerabilities with no available fix. Add a `.trivyignore` file to
suppress specific CVE IDs.

### `pip-audit.yml` — Dependency Audit

**Purpose.** Audits the exact locked dependency versions against the Python Packaging
Advisory Database (PyPI + OSV). Complements Dependabot: Dependabot proposes upgrades,
pip-audit fails the build when a known-vulnerable version is present.

**Triggers.** Push / PR that touches `pyproject.toml` or `uv.lock`, plus a **daily**
`cron` so newly disclosed CVEs surface even without code changes.

**Dependencies.**

| Type | Item |
| ---- | ---- |
| Actions | `astral-sh/setup-uv@v4` |
| Tools | `uv export`, `uvx pip-audit` |

**Configuration.** `uv export --frozen ... --all-groups` produces a requirements file
from the lockfile, then `pip-audit --strict --desc` audits it. Use `--ignore-vuln <ID>`
to accept a specific advisory that cannot yet be resolved.

---

## Build & Deploy

### `docker.yml` — Build & Push to GHCR

**Purpose.** Runs the test suite, then builds the production image and pushes it to the
GitHub Container Registry (`ghcr.io`).

**Triggers.** Push to `main`, version tags (`v*`), and pull requests to `main`. On PRs
the image is built but **not pushed**.

**How it works.** The `test` job must pass before `build-and-push` runs. Image tags are
derived automatically from the branch, semver tag, and commit SHA via
`docker/metadata-action`.

**Dependencies.**

| Type | Item |
| ---- | ---- |
| Actions | `docker/login-action@v3`, `docker/metadata-action@v5`, `docker/setup-buildx-action@v3`, `docker/build-push-action@v6` |
| Permissions | `packages: write` |
| Secrets | `GITHUB_TOKEN` (auto) |
| Cache | GitHub Actions cache (`type=gha`) |

**Configuration.** `REGISTRY` and `IMAGE_NAME` env vars control the destination. The
Dockerfile lives at `docker/Dockerfile`. See [Docker Deployment](docker.md) for how the
published image is consumed.

### `docs.yml` — Deploy Docs to GitHub Pages

**Purpose.** Builds this MkDocs site and deploys it to GitHub Pages.

**Triggers.** Push to `main` affecting `docs/**` or `mkdocs.yml`, plus manual
`workflow_dispatch`.

**How it works.** A `build` job installs the `docs` dependency group, runs
`mkdocs build --strict` (fails on broken links / nav), verifies `site/index.html`,
cleans up stale Pages artifacts, and uploads the site. A `deploy` job publishes it to the
`github-pages` environment.

**Dependencies.**

| Type | Item |
| ---- | ---- |
| Actions | `astral-sh/setup-uv@v4`, `actions/upload-pages-artifact@v4`, `actions/deploy-pages@v5` |
| Permissions | `pages: write`, `id-token: write`, `actions: write` |
| Repo setting | Pages source set to **GitHub Actions** |

**Configuration.** `--strict` means any broken cross-reference fails the build — keep the
`nav` in `mkdocs.yml` in sync with the files under `docs/`.

---

## Dependency Automation

### `dependabot.yml` — Automated Updates

**Purpose.** Opens pull requests to keep dependencies current, reducing exposure to
known vulnerabilities.

**Ecosystems.** Three update streams, all on a weekly schedule:

| Ecosystem | Directory | Watches |
| --------- | --------- | ------- |
| `uv` | `/` | `pyproject.toml` + `uv.lock` (native uv support) |
| `github-actions` | `/` | Action versions in `.github/workflows/` |
| `docker` | `/docker` | Base image in `docker/Dockerfile` |

**Configuration.** Python minor/patch updates are grouped into a single PR to reduce
noise; labels (`dependencies`, `python`, etc.) are applied automatically. The `uv`
ecosystem reads the committed `uv.lock` directly — keep it committed for Dependabot to
work.

---

## Repository setup

A few one-time settings unlock the full pipeline:

**Code scanning (CodeQL & Trivy).** Enable under **Settings → Code security → Code
scanning**. Public repositories get this for free; private repositories require GitHub
Advanced Security for SARIF uploads to appear in the Security tab.

**GitHub Pages (docs).** Under **Settings → Pages**, set the source to **GitHub
Actions**.

**Container registry (GHCR).** The `packages: write` permission is already declared in
`docker.yml`; no manual token is needed. Adjust package visibility under the repository's
**Packages** settings.

**Secrets.** None of the security or CI workflows need custom secrets — they all use the
automatically provided `GITHUB_TOKEN`. The only optional secret is `GITLEAKS_LICENSE`,
required **only** if the repository belongs to a GitHub Organization.
