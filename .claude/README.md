# DI Claude Base — cấu hình Claude Code dùng chung

Repo này chứa bộ cấu hình Claude Code chuẩn của công ty (project rules, subagents, skills, hooks bảo mật, MCP servers). Có hai cách dùng: **cài qua npm** (`@di/claude-base`, link vào `~/.claude/` — dùng chung cho mọi project trên máy) hoặc **đưa vào `.claude/` của một repo đích bằng `git subtree`** (per-repo). Xong là mọi dev có cùng một baseline.

---

## 0) Cài qua npm (`@di/claude-base`)

Cách này link cấu hình vào **`~/.claude/`** (user-level) nên dùng chung cho mọi project trên máy, thay vì nhúng vào từng repo.

Bước `postinstall` sẽ dựng layout sau:

```
~/.claude/
├── agents/
│   ├── shared/      → symlink tới package (DI-managed)
│   └── local/       ← thư mục thật, để bạn thêm agent riêng
├── skills/
│   ├── shared/      → symlink tới package (DI-managed)
│   └── local/       ← thư mục thật, để bạn thêm skill riêng
├── hooks/
│   └── shared/      → symlink tới package (DI-managed)
├── references/
│   └── shared/      → symlink tới package (DI-managed)
├── assets/
│   └── shared/      → symlink tới package (DI-managed)
└── settings.json    ← merge từ package; hook paths trỏ về ~/.claude/hooks/shared/scripts/

~/.mcp.json          ← merge từ package (mcpServers của bạn được giữ nguyên)
```

- `shared/` = **DI-managed**, đến từ package; đừng sửa tay (lần cài lại sẽ relink).
- `local/` = **của bạn**; postinstall không bao giờ đụng tới.
- Nếu `~/.claude/settings.json` hoặc `~/.mcp.json` đã có sẵn: postinstall **merge** — gộp `permissions.allow`/`ask` và `enabledMcpjsonServers` theo union, thay nguyên khối `hooks`, giữ server MCP tuỳ biến của bạn.

**Chạy lại bước link thủ công** (sau khi update package, hoặc nếu cần dựng lại symlink):

```bash
npx claude-base-link      # bất kỳ đâu sau khi đã cài
npm run link              # nếu đang ở trong repo này
```

**Windows**: tạo symlink cần **Developer Mode** hoặc chạy với quyền admin. Nếu không có quyền, postinstall tự fallback sang **copy file** — cấu hình vẫn dùng được nhưng **update sẽ không auto-propagate**, phải chạy lại `npx claude-base-link` sau mỗi lần đổi.

**Bỏ qua postinstall** (ví dụ trong CI):

```bash
CLAUDE_BASE_SKIP_POSTINSTALL=1 npm install
```

---

## 1) Có gì trong repo — giải thích từng phần

| Đường dẫn | Sau khi adopt | Vai trò |
|---|---|---|
| `CLAUDE.md` | `<repo>/.claude/CLAUDE.md` | **Project rules** — tech stack, 10 security rule, coding standards, workflow. Tự nạp vào mọi session như project memory. |
| `settings.json` | `<repo>/.claude/settings.json` | **Project settings** — `permissions` (allow/ask), wiring `hooks`, `enabledMcpjsonServers`. **Không pin `model`** (cố ý — xem note trong file). Lần đầu mở repo sẽ có trust prompt. |
| `.mcp.json` | **`<repo>/.mcp.json` (ROOT)** | Khai báo MCP servers. **Phải nằm ở root repo đích**, không phải trong `.claude/` — nên có bước đẩy ra ngoài (mục 2). |
| `agents/` | `<repo>/.claude/agents/` | 5 subagent của pipeline feature-workflow (xem bảng dưới). |
| `skills/` | `<repo>/.claude/skills/` | 11 skill theo stack + 2 skill điều phối workflow (xem bảng dưới). |
| `hooks/scripts/` | `<repo>/.claude/hooks/scripts/` | 2 script Node enforce security rule ở cấp harness. Chỉ chạy vì `settings.json` khai báo chúng. |
| `references/` | `<repo>/.claude/references/` | Tài liệu tham chiếu (vd `ticket-standard.md`). |
| `assets/` | `<repo>/.claude/assets/` | Input cho skill task-breakdown. `assets/template/` chứa file mẫu (app-spec, EVM report); `assets/app-spec.md` + `assets/backlog.xlsx` là file thật do con người điền (xem mục 6). |
| `.gitignore` | `<repo>/.claude/.gitignore` | Ignore của repo này; đi ké theo subtree, vô hại. |

### Agents (`.claude/agents/`)

Pipeline: `ticket-reader → planner → coder ↔ reviewer → tester`. Main agent điều phối, subagent **không** gọi lẫn nhau.

| Agent | Vai trò |
|---|---|
| `ticket-reader` | Đọc 1 work item Azure DevOps (qua MCP, fallback az CLI/WebFetch), xuất brief chuẩn hoá. Read-only. |
| `planner` | Sinh plan triển khai cho coder. Không viết code. |
| `coder` | Thực thi plan / sửa finding. Edit file, chạy linter + test hẹp. |
| `reviewer` | Review diff của coder → APPROVE / REQUEST_CHANGES. Chỉ báo cáo, không sửa. |
| `tester` | Viết test còn thiếu + chạy suite → ALL_GREEN / PRODUCTION_BUG_FOUND. |

### Skills (`.claude/skills/`)

| Skill | Khi nào dùng |
|---|---|
| `feature-workflow` | Điều phối toàn bộ vòng planner→coder→reviewer→tester cho 1 thay đổi (không kèm ticket). |
| `multi-ticket-workflow` | Như trên nhưng cho 1 hoặc nhiều ticket ADO, chạy tuần tự từng ticket. |
| `azure-devops-task-breakdown` | Tách app spec / backlog Excel thành Epic/Story/Task và tạo work item qua MCP. |
| `fastapi-endpoint` | Thêm/sửa route FastAPI theo layout api/schemas/services/models + auth + Pydantic. |
| `sqlalchemy-model` | Thêm/sửa bảng / model SQLAlchemy·SQLModel, async session, migration an toàn. |
| `react-component` | Thêm/sửa component React (functional + hooks, Tailwind, strict TS, a11y). |
| `pytest-suite` | Viết/mở rộng test pytest cho service FastAPI. |
| `playwright-e2e` | Viết/sửa test E2E Playwright (POM, mock network, selector ổn định). |
| `terraform-module` | Viết/sửa Terraform cho Azure (module layout, pinned provider, remote state). |
| `azure-pipeline` | Viết/sửa CI/CD (ADO Pipelines / GitHub Actions) — OIDC, pinned actions, Key Vault. |
| `secrets-scan` | Quét working tree/diff tìm secret, token, connection string, PII trước khi commit/push. |

### Hooks (`.claude/hooks/scripts/`)

Viết bằng **Node** (không `.sh`) để chạy đồng nhất trên Windows/macOS/Linux — `node` luôn đi kèm Claude Code. Chỉ kích hoạt vì `settings.json` khai báo chúng qua `${CLAUDE_PROJECT_DIR}/.claude/hooks/scripts/...`.

- `block-secret-paths.js` — PreToolUse cho `Read|Edit|Write|MultiEdit|NotebookEdit`: **deny** thao tác lên file giống secret (`.env`, `*.pem/*.key/*.pfx`, `secrets/`, `~/.ssh|.aws|.azure`, `*.tfvars`…). (CLAUDE.md #1)
- `guard-bash.cjs` — PreToolUse cho `Bash`: **deny** force-push và commit có secret; **ask** trước `terraform destroy` / `az group delete` / `DROP|TRUNCATE` / push lên nhánh được bảo vệ. (CLAUDE.md #2,#3,#4)

> Điều kiện chạy hook: máy có `node` trên PATH (mặc nhiên có cùng Claude Code).

---

## 2) Cài lên máy — step by step

### Bước 1 — Cài package

Package chưa publish lên npm registry công khai. Chọn một trong ba cách:

```bash
# Từ GitHub (sau khi PR merge vào main)
npm install github:Data-Impact-VN/DI-claude-base

# Từ local path (dev / test trước khi push)
npm install /path/to/DI-claude-base

# npm link (nếu bạn đang phát triển package này)
# trong repo DI-claude-base:
npm link
# trong project cần dùng:
npm link @di/claude-base
```

Bước `postinstall` chạy tự động và dựng layout `~/.claude/` + `~/.mcp.json` như mô tả ở mục 0.

Cuối quá trình, postinstall in bảng env vars cần thiết:

```
@di/claude-base — required environment variables
─────────────────────────────────────────────────
github (mcp):
  GITHUB_TOKEN          missing
azure-devops (mcp):
  AZURE_DEVOPS_ORG      missing
  AZURE_DEVOPS_PAT      missing
postgres (mcp):
  POSTGRES_READONLY_URL missing
playwright, filesystem, context7: no env vars required
─────────────────────────────────────────────────
```

### Bước 2 — Đặt env vars cho MCP servers

`.mcp.json` không chứa secret; nó đọc từ biến môi trường của shell. Thêm vào `~/.bashrc` / `~/.zshrc` (hoặc dùng `.env` + `direnv`):

| Server | Biến môi trường cần |
|---|---|
| `github` | `GITHUB_TOKEN` |
| `azure-devops` | `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PAT` |
| `postgres` | `POSTGRES_READONLY_URL` |
| `playwright`, `filesystem`, `context7` | (không cần) |

Bật/tắt server điều khiển bằng `enabledMcpjsonServers` trong `~/.claude/settings.json`.

### Bước 3 — Mở Claude Code & duyệt trust prompt

Lần đầu mở một project, Claude Code hỏi tin tưởng `~/.claude/settings.json` (vì có hooks + permissions). Chọn **Yes, I trust this folder**. Quyết định này lưu **theo từng máy**, không đi theo repo → mỗi dev tự duyệt một lần.

> Nếu chọn "No": Claude Code vẫn chạy nhưng **bỏ qua** settings + hooks (hook bảo mật sẽ không hoạt động).

---

## 2b) Tạo `assets/app-spec.md` từ template (con người tự làm)

Skill `azure-devops-task-breakdown` (Mode A — Kickoff) đọc app spec ở **`<repo>/.claude/assets/app-spec.md`**. File này mỗi project tự tạo và tự điền (đây là việc của con người, không phải Claude):

1. Copy file mẫu từ `~/.claude/assets/shared/template/app-spec-template.md` ra project:

```powershell
# Windows (PowerShell)
Copy-Item "$env:USERPROFILE\.claude\assets\shared\template\app-spec-template.md" .\.claude\assets\app-spec.md
```

```bash
# macOS / Linux
cp ~/.claude/assets/shared/template/app-spec-template.md .claude/assets/app-spec.md
```

2. Mở `assets/app-spec.md` và **điền nội dung** theo các heading của template. Tối thiểu cần: section 3 (mô tả chức năng theo module), section 8 (tech stack), section 9 (phases).
3. Lưu lại. Sau đó mới gọi skill `azure-devops-task-breakdown` để tách Epic/Story/Task.

> Tương tự, backlog (Mode B) dùng `assets/backlog.xlsx` — copy/điền từ mẫu `~/.claude/assets/shared/template/` nếu cần.

---

## 3) Verify sau khi cài

Mở Claude Code trong bất kỳ project nào, kiểm tra:

- `/agents` → thấy `planner`, `coder`, `reviewer`, `tester`, `ticket-reader`.
- Gõ `/` → thấy các skill (`feature-workflow`, `fastapi-endpoint`, …).
- `/mcp` → thấy các MCP server đã bật (và trạng thái auth).
- Thử hook: yêu cầu đọc một file `.env` → phải bị **deny** với lý do từ `block-secret-paths.js`.

---

## 4) Cập nhật khi base config thay đổi

```bash
# Từ GitHub
npm update @di/claude-base

# Từ local path (nếu dùng file:)
npm install /path/to/DI-claude-base
```

Bước `postinstall` chạy lại tự động — relink symlinks và merge settings/mcp.json. Hoặc chạy thủ công bất cứ lúc nào:

```bash
npx claude-base-link
```

---

## 5) Tinh chỉnh & lưu ý

- **Bỏ phần thừa**: project nào không dùng Terraform/React… có thể xoá skill tương ứng trong `.claude/skills/` và bớt allowlist trong `.claude/settings.json`. (Lưu ý: lần `subtree pull` sau có thể kéo lại — cân nhắc giữ nguyên và chỉ tắt qua settings.)
- **Override cá nhân**: tạo `.claude/settings.local.json` (đã được `.gitignore`) cho cấu hình riêng từng dev — ưu tiên cao hơn `settings.json`. Ví dụ muốn cố định model: đặt `"model"` ở đây (không đặt trong `settings.json` chung, sẽ ghi đè lựa chọn `/model` của mọi người).
- **Model**: `settings.json` cố ý không pin `model` để dùng default theo account tier + auto routing và giữ lựa chọn `/model` của từng dev.
- **File "đi ké"**: `.claude/README.md`, `.claude/.gitignore` theo subtree vào — vô hại, xoá được nếu muốn gọn.
- **Không commit secret**: `.mcp.json` chỉ tham chiếu env var; tuyệt đối không hard-code token vào đó.
