# CI/CD & GitHub Actions

Dự án đi kèm một bộ workflow GitHub Actions trong `.github/workflows/`, bao phủ toàn bộ
vòng đời phân phối phần mềm: kiểm tra chất lượng, quét bảo mật, build container, deploy
tài liệu, và tự động cập nhật dependency.

Tất cả workflow chạy trên `ubuntu-latest`, dùng [`uv`](https://docs.astral.sh/uv/) cho
tooling Python, và xác thực bằng `GITHUB_TOKEN` tích hợp sẵn — **không cần thêm secret
nào** để chạy các pipeline bảo mật và CI.

## Tổng quan

| Workflow | File | Kích hoạt | Mục đích |
| -------- | ---- | --------- | -------- |
| **CI** | `ci.yml` | Push / PR vào `main` | Lint, format, type check, test + coverage |
| **CodeQL** | `codeql.yml` | Push / PR vào `main`, hàng tuần | Phân tích tĩnh (SAST) cho Python |
| **Secret Scan** | `gitleaks.yml` | Push / PR vào `main`, hàng tuần | Phát hiện secret bị lộ trong lịch sử git |
| **Bandit** | `bandit.yml` | Push / PR vào `main`, hàng tuần | Linter bảo mật cho Python |
| **Trivy** | `trivy.yml` | Push / PR vào `main`, hàng tuần | Quét lỗ hổng + IaC + image |
| **Dependency Audit** | `pip-audit.yml` | Đổi dependency, hàng ngày | Audit CVE cho dependency đã khóa |
| **Build & Push** | `docker.yml` | Push `main`/tag, PR | Test rồi build & push image lên GHCR |
| **Deploy Docs** | `docs.yml` | Push `main` (docs), thủ công | Build MkDocs và deploy lên GitHub Pages |
| **Dependabot** | `dependabot.yml` | Theo lịch | Tự động tạo PR cập nhật dependency |

!!! note "Thiết lập repository"
    Một số workflow đẩy kết quả lên tab **Security** của GitHub và cần bật code scanning.
    Xem [Thiết lập repository](#thiet-lap-repository) ở cuối trang.

---

## CI & Chất lượng

### `ci.yml` — Continuous Integration

**Mục đích.** Cổng kiểm tra chất lượng chính. Chặn merge khi lint (`ruff check`) hoặc bộ
test thất bại, đồng thời tạo báo cáo coverage. Format và type check chạy ở mức advisory.

**Kích hoạt.** Push và pull request nhắm vào `main`. Các lần chạy trùng trên cùng một ref
sẽ bị hủy để tiết kiệm thời gian.

**Cách hoạt động.** Hai job chạy song song:

- **`lint`** — cài `uv`, sau đó chạy `ruff check` (lint, **chặn build**), `ruff format
  --check` (format) và `mypy` (type check). Vì codebase chưa áp dụng formatter của ruff
  cũng như chưa từng type-check trong CI, cả `ruff format --check` và `mypy` đều để
  `continue-on-error: true` (advisory) — chỉ báo cáo, không chặn build. Chạy
  `uvx ruff format .` ở máy, rồi đổi từng cái thành `false` khi đã sạch.
- **`test`** — matrix qua Python **3.11** và **3.12**. Job khởi động một **service
  container** `pgvector/pgvector:pg16`, bật extension `vector`, rồi chạy `pytest` kèm
  coverage (`pytest-cov`). File coverage XML được upload làm artifact.

**Phụ thuộc.**

| Loại | Thành phần |
| ---- | ---------- |
| Actions | `actions/checkout@v4`, `astral-sh/setup-uv@v4`, `actions/upload-artifact@v4` |
| Công cụ (qua `uvx`) | `ruff`, `mypy`, `pytest-cov` |
| Service container | `pgvector/pgvector:pg16` |
| Secret | Không (API key giả được truyền dưới dạng literal) |

**Cấu hình.**

- Biến `DATABASE_URL` trỏ test tới service container. Các key LLM giả
  (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GEMINI_API_KEY`) được đặt
  `test-key` để code đọc config/import không lỗi — bộ unit test không cần key thật.
- `pyproject.toml` đã có sẵn mục `[tool.ruff]` (`target-version = "py311"`,
  `line-length = 100`); mở rộng nó (hoặc thêm `[tool.mypy]`) để tùy chỉnh rule — workflow
  tự động áp dụng.
- Sửa danh sách `matrix.python-version` để đổi phiên bản Python được test.

---

## Bảo mật

### `codeql.yml` — CodeQL (SAST)

**Mục đích.** Công cụ phân tích tĩnh chính chủ của GitHub. Phát hiện injection,
deserialization không an toàn, path traversal và các loại lỗ hổng khác trong code Python,
rồi đẩy cảnh báo lên tab Security.

**Kích hoạt.** Push / PR vào `main`, cộng thêm `cron` hàng tuần (thứ Hai) để các query mới
công bố vẫn chạy dù không có thay đổi code.

**Phụ thuộc.**

| Loại | Thành phần |
| ---- | ---------- |
| Actions | `github/codeql-action/init@v3`, `github/codeql-action/analyze@v3` |
| Quyền | `security-events: write` |
| Cài đặt repo | Bật code scanning (xem [Thiết lập repository](#thiet-lap-repository)) |

**Cấu hình.** Phân tích `languages: python` với bộ query `security-and-quality`. Đổi sang
`security-extended` để có nhiều rule hơn, hoặc thêm `paths-ignore` để bỏ qua code sinh
tự động.

### `gitleaks.yml` — Quét Secret

**Mục đích.** Scanner giá trị nhất với dự án này. Vì repo có file `.env` và tích hợp
Anthropic, OpenAI, Google cùng `DATABASE_URL`, một key bị commit là rủi ro thật. gitleaks
quét **toàn bộ lịch sử git**, không chỉ diff.

**Kích hoạt.** Push / PR vào `main`, cộng thêm `cron` hàng tuần.

**Phụ thuộc.**

| Loại | Thành phần |
| ---- | ---------- |
| Actions | `gitleaks/gitleaks-action@v2` |
| Checkout | `fetch-depth: 0` (cần toàn bộ lịch sử) |
| Secret | `GITHUB_TOKEN` (tự động). `GITLEAKS_LICENSE` **chỉ** cần cho GitHub Organization |

**Cấu hình.** Thêm file `.gitleaks.toml` ở gốc repo để tùy chỉnh rule hoặc allowlist các
false positive đã biết (ví dụ giá trị placeholder trong `.env.example`).

### `bandit.yml` — Lint Bảo mật Python

**Mục đích.** Linter bảo mật tĩnh chuyên cho Python. Đặc biệt phù hợp vì có crawler
(`httpx`, `lxml` parse HTML không tin cậy) và service FastAPI. Bắt các pattern như `eval`,
parse XML không an toàn, dùng `subprocess` sai, và secret hardcode.

**Kích hoạt.** Push / PR vào `main`, cộng thêm `cron` hàng tuần.

**Phụ thuộc.**

| Loại | Thành phần |
| ---- | ---------- |
| Actions | `astral-sh/setup-uv@v4` |
| Công cụ (qua `uvx`) | `bandit` |

**Cấu hình.** Quét `src api scripts` (loại trừ tests vì `assert` là bình thường ở đó). Cờ
`-ll -ii` giới hạn kết quả ở **severity từ MEDIUM** và **confidence từ MEDIUM** để giữ tín
hiệu cao. `-s B608` bỏ qua check chuỗi SQL: table name được nội suy từ config nội bộ tin
cậy, còn mọi giá trị đều truyền qua placeholder `%s`. Cùng skip này được ghi lại trong mục
`[tool.bandit]` của `pyproject.toml` để chạy local đồng nhất.

### `trivy.yml` — Quét Lỗ hổng & IaC

**Mục đích.** Scanner supply-chain và hạ tầng phạm vi rộng. Hai job:

- **`repo-scan`** — quét filesystem của repo tìm dependency có lỗ hổng, cấu hình sai và
  secret bị lộ.
- **`image-scan`** — build Docker image cục bộ (không push) và quét chính image sẽ phát
  hành, bao gồm cả package hệ điều hành.

Cả hai upload kết quả SARIF lên tab Security.

**Kích hoạt.** Push / PR vào `main`, cộng thêm `cron` hàng tuần.

**Phụ thuộc.**

| Loại | Thành phần |
| ---- | ---------- |
| Actions | `aquasecurity/trivy-action@v0.36.0`, `docker/setup-buildx-action@v3`, `docker/build-push-action@v6`, `github/codeql-action/upload-sarif@v3` |
| Quyền | `security-events: write` |
| Cache | GitHub Actions cache (`type=gha`) cho bước build Docker |
| Cài đặt repo | Bật code scanning (để upload SARIF) |

**Cấu hình.** Severity giới hạn ở `CRITICAL,HIGH`; `ignore-unfixed: true` ở image scan ẩn
các lỗ hổng chưa có bản vá. Thêm file `.trivyignore` để bỏ qua các CVE ID cụ thể.

### `pip-audit.yml` — Audit Dependency

**Mục đích.** Audit đúng phiên bản dependency đã khóa so với Python Packaging Advisory
Database (PyPI + OSV). Bổ trợ cho Dependabot: Dependabot đề xuất nâng cấp, còn pip-audit
làm fail build khi có phiên bản đã biết lỗ hổng.

**Kích hoạt.** Push / PR chạm vào `pyproject.toml` hoặc `uv.lock`, cộng thêm `cron`
**hàng ngày** để CVE mới công bố vẫn lộ ra dù không đổi code.

**Phụ thuộc.**

| Loại | Thành phần |
| ---- | ---------- |
| Actions | `astral-sh/setup-uv@v4` |
| Công cụ | `uv export`, `uvx pip-audit` |

**Cấu hình.** `uv export --frozen ... --all-groups` tạo file requirements từ lockfile, rồi
`pip-audit --strict --desc` audit nó. Hiện đang truyền `--ignore-vuln PYSEC-2026-311` — một
advisory chưa có bản vá trong package `chromadb` cũ không còn dùng (project dùng pgvector);
chạy `uv lock` để loại chromadb khỏi lockfile rồi bỏ dòng ignore đi. Thêm các cờ
`--ignore-vuln <ID>` khác cho những advisory chưa thể xử lý.

---

## Build & Deploy

### `docker.yml` — Build & Push lên GHCR

**Mục đích.** Chạy bộ test, rồi build image production và push lên GitHub Container
Registry (`ghcr.io`).

**Kích hoạt.** Push vào `main`, tag phiên bản (`v*`), và pull request vào `main`. Với PR
thì image được build nhưng **không push**.

**Cách hoạt động.** Job `test` phải pass trước khi `build-and-push` chạy. Tag image được
suy ra tự động từ branch, tag semver và commit SHA qua `docker/metadata-action`.

**Phụ thuộc.**

| Loại | Thành phần |
| ---- | ---------- |
| Actions | `docker/login-action@v3`, `docker/metadata-action@v5`, `docker/setup-buildx-action@v3`, `docker/build-push-action@v6` |
| Quyền | `packages: write` |
| Secret | `GITHUB_TOKEN` (tự động) |
| Cache | GitHub Actions cache (`type=gha`) |

**Cấu hình.** Biến `REGISTRY` và `IMAGE_NAME` điều khiển đích đến. Dockerfile nằm ở
`docker/Dockerfile`. Xem [Triển khai Docker](docker.md) để biết cách dùng image đã publish.

### `docs.yml` — Deploy Docs lên GitHub Pages

**Mục đích.** Build trang MkDocs này và deploy lên GitHub Pages.

**Kích hoạt.** Push vào `main` ảnh hưởng `docs/**` hoặc `mkdocs.yml`, cộng thêm
`workflow_dispatch` thủ công.

**Cách hoạt động.** Job `build` cài nhóm dependency `docs`, chạy `mkdocs build --strict`
(fail nếu có link/nav hỏng), kiểm tra `site/index.html`, dọn artifact Pages cũ, rồi upload
site. Job `deploy` publish nó lên environment `github-pages`.

**Phụ thuộc.**

| Loại | Thành phần |
| ---- | ---------- |
| Actions | `astral-sh/setup-uv@v4`, `actions/upload-pages-artifact@v4`, `actions/deploy-pages@v5` |
| Quyền | `pages: write`, `id-token: write`, `actions: write` |
| Cài đặt repo | Nguồn Pages đặt là **GitHub Actions** |

**Cấu hình.** `--strict` nghĩa là bất kỳ tham chiếu chéo hỏng nào cũng làm fail build —
giữ `nav` trong `mkdocs.yml` đồng bộ với các file trong `docs/`. Khối `concurrency` dùng
`cancel-in-progress: false` để lần deploy đang chạy được hoàn tất thay vì bị hủy giữa chừng
(việc hủy dễ khiến Pages rơi vào trạng thái lỗi "try again later").

---

## Tự động hóa Dependency

### `dependabot.yml` — Cập nhật Tự động

**Mục đích.** Mở pull request để giữ dependency luôn mới, giảm rủi ro từ các lỗ hổng đã
biết.

**Ecosystem.** Ba luồng cập nhật (`uv` và `github-actions` hàng tuần, `docker` hàng tháng):

| Ecosystem | Thư mục | Lịch | Theo dõi |
| --------- | ------- | ---- | -------- |
| `uv` | `/` | hàng tuần | `pyproject.toml` + `uv.lock` (hỗ trợ uv gốc) |
| `github-actions` | `/` | hàng tuần | Phiên bản action trong `.github/workflows/` |
| `docker` | `/docker` | hàng tháng | Base image trong `docker/Dockerfile` |

**Cấu hình.** Cập nhật minor/patch của Python được gộp vào một PR để giảm nhiễu; label
(`dependencies`, `python`, ...) được gắn tự động. Ecosystem `uv` đọc trực tiếp `uv.lock`
đã commit — hãy giữ nó được commit để Dependabot hoạt động.

---

## Thiết lập repository

Một vài cài đặt một lần sẽ mở khóa toàn bộ pipeline:

**Code scanning (CodeQL & Trivy).** Bật ở **Settings → Code security → Code scanning**.
Repo public được miễn phí; repo private cần GitHub Advanced Security để kết quả SARIF hiện
trong tab Security.

**GitHub Pages (docs).** Ở **Settings → Pages**, đặt nguồn là **GitHub Actions**.

**Container registry (GHCR).** Quyền `packages: write` đã khai báo trong `docker.yml`;
không cần token thủ công. Chỉnh mức hiển thị package ở phần **Packages** của repo.

**Secrets.** Không workflow bảo mật hay CI nào cần secret tùy chỉnh — tất cả dùng
`GITHUB_TOKEN` được cấp tự động. Secret tùy chọn duy nhất là `GITLEAKS_LICENSE`, **chỉ**
cần nếu repo thuộc một GitHub Organization.
