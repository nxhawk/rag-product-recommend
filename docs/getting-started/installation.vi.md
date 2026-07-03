# Cài đặt

## Yêu cầu

- Python 3.11+
- Trình quản lý gói [uv](https://docs.astral.sh/uv/)
- API key cho Anthropic và/hoặc OpenAI

## Cài đặt uv

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

=== "macOS / Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

## Clone và cài đặt

```bash
git clone https://github.com/nxhawk/rag-product-recommend.git
cd rag-product-recommend
uv sync
```

Lệnh này cài đặt toàn bộ dependencies từ `pyproject.toml` và tự động tạo virtual environment (tương tự `npm install`).

## Biến môi trường

Sao chép file env mẫu và điền API key của bạn:

```bash
cp .env.example .env
```

Các biến bắt buộc:

| Biến                  | Mô tả                       |
| --------------------- | --------------------------- |
| `ANTHROPIC_API_KEY`   | API key của Anthropic       |
| `OPENAI_API_KEY`      | API key của OpenAI (embedding) |

## Cài đặt dependencies cho Dev

```bash
uv sync --group dev
```

## Cài đặt dependencies cho Docs

```bash
uv sync --group docs
```
