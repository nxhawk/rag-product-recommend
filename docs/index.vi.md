# RAG Product Recommendation

Hệ thống gợi ý và so sánh sản phẩm được xây dựng trên nền tảng **Retrieval-Augmented Generation (RAG)**.

Người dùng đặt câu hỏi bằng ngôn ngữ tự nhiên, hệ thống truy xuất dữ liệu sản phẩm liên quan từ vector database, sau đó LLM tạo ra câu trả lời có ngữ cảnh và lập luận rõ ràng.

## Tính năng chính

- **Gợi ý sản phẩm** — Phân tích ý định người dùng (ngân sách, mục đích, ưu tiên), truy xuất sản phẩm phù hợp, chấm điểm và xếp hạng, sau đó sinh giải thích qua LLM.
- **So sánh sản phẩm** — Đối chiếu thông số kỹ thuật giữa các sản phẩm, so sánh từng tiêu chí, đưa ra phân tích chi tiết kèm ưu/nhược điểm và kết luận.
- **Tìm kiếm thông minh** — Kết hợp tìm kiếm ngữ nghĩa (semantic), khớp từ khóa và lọc theo metadata, có rerank bằng cross-encoder.
- **LLM đa nhà cung cấp** — Hỗ trợ cả Anthropic Claude và OpenAI GPT làm backend sinh câu trả lời.

## Liên kết nhanh

- [Cài đặt](getting-started/installation.md)
- [Bắt đầu nhanh](getting-started/quickstart.md)
- [Tổng quan kiến trúc](architecture/overview.md)
- [Tài liệu API](api/endpoints.md)
