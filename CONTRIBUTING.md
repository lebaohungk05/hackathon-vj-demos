# Đóng góp

## Quy trình nhánh

- `main` và `dev` được bảo vệ. **Không push thẳng**, mọi thay đổi đi qua Pull Request.
- Luôn cắt nhánh từ `dev` mới nhất và mở PR vào `dev`:

```bash
git fetch origin && git switch dev && git pull origin dev
git switch -c feat/mo-ta-ngan        # feat/, fix/, refactor/, docs/, chore/, ci/
# ... sửa, commit ...
git push -u origin feat/mo-ta-ngan
gh pr create --base dev
```

- Sau khi PR được merge, xóa nhánh ở cả local và remote:

```bash
git switch dev && git pull origin dev
git branch -d feat/mo-ta-ngan
git push origin --delete feat/mo-ta-ngan
git fetch --prune origin
```

## Commit

Theo [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): mô tả ngắn, thể mệnh lệnh`, ví dụ `fix(llm): handle empty reply from the CLI`. Một commit nên là một thay đổi có thể hiểu độc lập. Ghi mã ticket (`AB#1234`) vào tên nhánh và commit nếu có.

## Môi trường

```bash
python -m venv .venv && .venv\Scripts\Activate.ps1      # Windows; macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## Trước khi mở PR

```bash
ruff check src tests scripts
pytest                          # unit test
pytest tests/e2e -m e2e         # Playwright smoke test, chạy offline
```

CI chạy lại các lệnh này trên Python 3.10 và 3.12.

## Những điều cần cẩn thận

- **Không đổi chuỗi prompt, schema hay byte của ảnh thử** trong `data/vision/testset/` nếu không sinh lại cache. Khóa cache LLM là hash của prompt và dữ liệu; đổi một ký tự sẽ làm demo rơi về bộ quy tắc ở chế độ offline. Xem [ADR 0003](docs/design/adr/0003-committed-deterministic-caches.md).
- **Giữ ranh giới LLM và công cụ tất định.** LLM không được duyệt lịch, sửa số đo hay tự đặt ngưỡng nước. Xem [kiến trúc](docs/design/architecture.md).
- Không đưa bí mật, token hay dữ liệu cá nhân vào repo. File sinh khi chạy nằm trong `.cache/` và bị git bỏ qua.
- Cập nhật tài liệu trong `docs/` khi đổi hành vi hoặc cấu trúc.
