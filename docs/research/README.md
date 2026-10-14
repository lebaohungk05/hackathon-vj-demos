# Nghiên cứu

## Bài toán

Tưới ướt khô xen kẽ (AWD) phải làm chung cho cả cụm ruộng dùng một trạm bơm, nên hộ nào cũng khó tự quyết. Nông dân và cán bộ HTX phải ra ruộng đọc ống đo mực nước, trong khi doanh nghiệp làm tín chỉ carbon cần bằng chứng từng thửa. RiceBridge Ops biến các số đo rời rạc (ảnh, cảm biến, lời báo miệng, dự báo mưa) thành lịch bơm hằng ngày cho cả cụm và hồ sơ bằng chứng cho từng thửa. Nội dung đầy đủ nằm trong bản đề xuất ý tưởng (Idea Proposal, VJAI Hackathon 2026).

## Kết quả mô phỏng

Mô phỏng 5 cụm × 6 thửa, 20 lần chạy kiểm tra, mưa và bốc hơi lấy từ Open-Meteo vụ Đông Xuân 2025–26. Chạy bằng `python -m ricebridge.sim.experiment test` rồi `python -m ricebridge.sim.report`.

- Kết quả đầy đủ: [`outputs/sim/test/results.md`](../../outputs/sim/test/results.md)
- Hình: `outputs/sim/test/fig_agent_vs_baseline.png`, `fig_cluster_trace.png`
- Độ nhạy theo công suất trạm bơm: `outputs/sim/test/sensitivity_pump_capacity.json`

Điều cần nhớ khi trích dẫn các con số này:

- Chúng đến từ bộ quy tắc cố định chạy cùng ba công cụ tất định (cân bằng nước, an toàn theo giai đoạn lúa, xếp lịch theo công suất trạm), chưa có LLM. Demo dùng LLM để hiểu ngôn ngữ và soạn tin nhắn, còn quyết định về nước vẫn do công cụ tất định đưa ra.
- Mô phỏng biết trước mực nước thật. Các lỗi (cảm biến trôi, ảnh đọc sai, đổi lịch bơm) do nhóm cài sẵn, nên tỷ lệ bắt lỗi không dùng để dự đoán kết quả ngoài ruộng.
- Mô phỏng không tính methane, năng suất hay tín chỉ.

## Nguồn dữ liệu trong repo

| Dữ liệu | Vị trí | Ghi chú |
| --- | --- | --- |
| Mưa và ET0 Long Xuyên, 16/02–12/03/2026 | `data/fixtures/open_meteo_an_giang_2026-02-16_2026-03-12.json` | Open-Meteo Historical Weather API, dùng cho demo |
| Mưa và ET0 An Giang, Cần Thơ, 12/2025–03/2026 | `data/fixtures/sim_weather_*.csv` | Đầu vào của mô phỏng |
| Ảnh ống đo | `data/vision/testset/` | Ảnh tổng hợp, không phải ảnh ngoài ruộng. Xem [công cụ đọc ảnh](../manual/vision-tools.md) |
| Câu trả lời LLM đã cache | `data/llm_cache/`, `data/i18n/` | Cố ý commit để demo chạy offline. Xem [ADR 0003](../design/adr/0003-committed-deterministic-caches.md) |
