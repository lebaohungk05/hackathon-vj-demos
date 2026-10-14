import json
from pathlib import Path

OUT = Path(__file__).parent / "out" / "test"

ROWS = [
    ("awd_violation_plot_days", "Ngày-thửa khô quá ngưỡng AWD (dưới −15 cm quá 2 ngày, hoặc ruộng thoát nước kém khô quá 10 ngày)", 1),
    ("heading_dry_plot_days", "Ngày-thửa khô lúc trổ bông (dưới −5 cm), rủi ro năng suất", 1),
    ("topdress_dry_plot_days", "Ngày-thửa khô ngay sau bón thúc (dưới −5 cm)", 1),
    ("awd_drying_plot_days", "Ngày-thửa có mặt ruộng khô trong giai đoạn được phép AWD (mức độ thực hành AWD)", 0),
    ("evidence_completeness_pct", "Độ đầy đủ bằng chứng: % khối 3 ngày có ít nhất 1 số đo đúng ±3 cm", 1),
    ("pump_days_used", "Số ngày trạm bơm chạy (5 cụm, cả vụ)", 0),
    ("plot_irrigations", "Số lượt bơm cho từng thửa", 0),
    ("water_applied_mm_per_plot", "Nước bơm vào mỗi thửa (mm/vụ)", 0),
    ("remeasure_requests_per_plot_week", "Yêu cầu đo lại mỗi thửa mỗi tuần (gánh nặng cho nông dân)", 2),
    ("officer_visits_per_plot_week", "Lượt cán bộ HTX đi đo mỗi thửa mỗi tuần", 2),
    ("awd_deep_plot_days", "Ngày-thửa giai đoạn AWD sâu hơn −15 cm", 1),
]

DETECTION = [
    ("a_sensor", "(a) Cảm biến trôi số hoặc kẹt số"),
    ("b_missing_logs", "(b) Mất nhật ký từ 3 ngày (recall tính trên khoảng mất được cấy vào)"),
    ("c_photo_misread", "(c) Ảnh đọc sai, mâu thuẫn cảm biến"),
    ("d_pump_schedule", "(d) Lịch bơm đổi (báo trước hoặc bơm hỏng không báo)"),
]


def cell(summary, key, digits=1):
    s = summary.get(key)
    if s is None:
        return "–"
    fmt = f"{{:.{digits}f}}"
    return f"{fmt.format(s['mean'])} [{fmt.format(s['min'])}–{fmt.format(s['max'])}]"


def main():
    res = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    sens = json.loads((OUT / "sensitivity_pump_capacity.json").read_text(encoding="utf-8"))
    s = res["summary"]
    lines = [
        "# RiceBridge Ops: kết quả đo trên mô phỏng có nhãn",
        "",
        f"Mọi con số dưới đây là **kết quả mô phỏng**, không phải dữ liệu ruộng thật. Đầu vào thật duy nhất là thời tiết ngày (Open-Meteo, Đông Xuân 2025-26). 30 thửa (5 cụm × 6 thửa chung 1 trạm bơm), {len(res['seeds'])} seed kiểm tra ({res['seeds'][0]}–{res['seeds'][-1]}). Agent được chỉnh trên seed 0–9 và không chỉnh thêm sau khi chạy seed kiểm tra. Mỗi ô: trung bình [min–max] qua các seed.",
        "",
        "## Vận hành nước và bằng chứng",
        "",
        "| Chỉ số | Lịch cố định | Lịch cố định + cán bộ đo trước mỗi lượt bơm | Agent (bản đầu) | Agent (bản chỉnh trên seed phát triển) | Chỉ lập lịch, không kiểm tra chéo | Biết mực nước thật (mốc tham chiếu) |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, label, digits in ROWS:
        lines.append(f"| {label} | {cell(s['baseline'], key, digits)} | {cell(s['checklist'], key, digits)} | {cell(s['agent'], key, digits)} | **{cell(s['agent_risk'], key, digits)}** | {cell(s['planner_only'], key, digits)} | {cell(s['oracle'], key, digits)} |")
    lines += [
        "",
        "## Phát hiện lỗi (agent; lịch cố định không có bước kiểm tra nên recall = 0)",
        "",
        "| Loại lỗi | Số sự kiện/seed | Precision | Recall | Thời gian phát hiện (ngày) |",
        "|---|---|---|---|---|",
    ]
    for key, label in DETECTION:
        a = lambda m: cell(s["agent"], f"detection.{key}.{m}", 2)
        lines.append(f"| {label} | {cell(s['agent'], f'detection.{key}.events', 1)} | {a('precision')} | {a('recall')} | {a('mean_ttd_days')} |")
    lines += [
        f"| (e) HTX ghi hộ cho nông dân lớn tuổi (không phải lỗi) | 5 thửa | Agent gắn cờ nhầm: {cell(s['agent'], 'detection.e_proxy_false_flags_agent', 0)} | Quy tắc chỉ đếm nhật ký của chính nông dân sẽ gắn cờ nhầm: {cell(s['agent'], 'detection.e_proxy_false_flags_naive_farmer_only_rule', 0)} | – |",
        "",
        "Thời gian phát hiện của (d): −1 nghĩa là agent lập lại kế hoạch 1 ngày trước ngày bơm cũ, khi HTX báo trước; +1 nghĩa là agent phát hiện bơm hỏng vào sáng hôm sau, khi không có xác nhận bơm. (b) và (d) là quy tắc đếm và đối chiếu lịch, nên đạt gần như tuyệt đối theo cách dựng mô phỏng. Phần đáng đo là (a) và (c).",
        "",
        "## Độ nhạy theo công suất trạm bơm (thửa/ngày chạy, 2 ngày chạy/tuần)",
        "",
        "| Công suất | Chỉ số | Lịch cố định | Agent | Biết mực nước thật |",
        "|---|---|---|---|---|",
    ]
    for cap, res_cap in sens.items():
        for key, label in (("awd_violation_plot_days", "Khô quá ngưỡng AWD"), ("heading_dry_plot_days", "Khô lúc trổ bông"), ("pump_days_used", "Ngày bơm chạy")):
            lines.append(f"| {cap} | {label} | {cell(res_cap['baseline'], key)} | {cell(res_cap['agent'], key)} | {cell(res_cap['oracle'], key)} |")
    lines += [
        "",
        "Hình: `fig_cluster_trace.png` (một cụm, mưa thật, mực nước thật trong mô phỏng, hành động của agent), `fig_agent_vs_baseline.png` (so sánh các chỉ số chính).",
        "",
        "## Đầu vào thật và giả định",
        "",
        "**Thật (đã kiểm):** mưa ngày `precipitation_sum` và ET0 FAO `et0_fao_evapotranspiration`, Open-Meteo Historical Weather API (https://archive-api.open-meteo.com/v1/archive), An Giang (10.37, 105.43) và Cần Thơ (10.03, 105.78), 01/12/2025–31/03/2026. Kc lúa theo FAO-56 Bảng 12 (https://www.fao.org/4/x0490e/x0490e0b.htm): ban đầu 1.05, giữa vụ 1.20, cuối vụ 0.90–0.60 (dùng 0.90). Ngưỡng Safe AWD theo JIRCAS như trong proposal: tưới lại khi nước xuống −15 cm, không để khô lúc trổ bông và sau bón thúc, giới hạn số ngày khô cho ruộng thoát nước kém.",
        "",
        "**Giả định (chưa kiểm chứng ngoài đồng):** vụ 105 ngày; mốc giai đoạn (ngày sau sạ): 0–19 ổn định, giữ nước; 20–24 và 40–44 sau bón thúc, giữ nước; 60–79 trổ bông, giữ nước; 95–104 rút nước cuối vụ; còn lại cho phép AWD. Kc giai đoạn phát triển nội suy 1.05→1.20 (ngày 20–39) và cuối vụ 1.20→0.90 (ngày 80–104). FAO-56 Bảng 11 ghi vụ lúa nhiệt đới 150 ngày; vụ 105 ngày là giả định cho giống ngắn ngày ở ĐBSCL. Thấm 1–5 mm/ngày, rò bờ 0.5–1.5 mm/ngày, hệ số nhả nước khi mực nước dưới mặt đất 0.20–0.30, mỗi thửa rút ngẫu nhiên. Ruộng thoát nước kém khi thấm dưới 2 mm/ngày; giới hạn khô 10 ngày. Bơm lên +5 cm; bờ 15 cm. Trạm bơm chạy thứ Hai và thứ Năm, 4 thửa/ngày chạy. Mỗi cụm có 2/6 thửa gắn cảm biến (nhiễu 0.7 cm), 1 thửa do HTX ghi hộ 2 ngày/lần. Nông dân ghi nhật ký 85% số ngày, có ảnh ống đo trong 50% số đó (sai số đọc 1 cm); làm theo yêu cầu đo lại 90%. Tỉ lệ lỗi: 50% cảm biến hỏng một lần (trôi 0.6–1.2 cm/ngày hoặc kẹt số); 8% ảnh trên thửa có cảm biến bị đọc sai 6–12 cm; 2 khoảng mất nhật ký 3–7 ngày mỗi cụm; 2 lần đổi lịch bơm mỗi cụm (một nửa báo trước 1 ngày, một nửa bơm hỏng không báo). Dự báo mưa 2 ngày bằng mưa thật nhân hệ số ngẫu nhiên 0.5–1.5. Kỹ thuật viên sửa cảm biến 3 ngày sau khi bị gắn cờ; lịch cố định không gắn cờ nên lỗi kéo dài hết vụ.",
        "",
        "## Giới hạn",
        "",
        "- Mô hình cân bằng nước một lớp, không mô phỏng ET giảm khi đất khô, không có dòng chảy giữa các thửa, mực nước thấp nhất −40 cm.",
        "- Lỗi được cấy theo xác suất do nhóm tự đặt. Precision và recall phụ thuộc trực tiếp vào cách cấy lỗi, nên không phải con số dự đoán ngoài đồng.",
        "- Agent dùng quy tắc tất định. Ngưỡng do nhóm chỉnh trên seed phát triển; ngoài đồng phải hiệu chỉnh lại theo từng thửa.",
        "- Mô phỏng không đo CH4, năng suất hay tín chỉ. Số ngày khô trong giai đoạn AWD chỉ là chỉ báo gián tiếp. Agent giữ ruộng ướt hơn lịch cố định, nên có thể làm giảm mức giảm phát thải. Thửa khô quá ngưỡng của lịch cố định cũng không phải AWD an toàn.",
        "- Khô lúc trổ bông bị chặn chủ yếu bởi công suất trạm bơm: ngay cả chính sách biết mực nước thật vẫn còn khoảng ngang agent. Agent không tạo thêm công suất bơm.",
        "- Mốc thứ hai (lịch cố định + cán bộ đo trước mỗi lượt bơm): cán bộ HTX đo ống của mọi thửa trong cụm sáng ngày bơm (sai số 1 cm), giữa các lượt dùng số đọc gần nhất của nông dân hoặc cảm biến, không đối chiếu nguồn; bơm cho thửa đang cần giữ nước khi dưới +3 cm, thửa AWD khi từ −5 cm trở xuống, thửa trổ bông ưu tiên, rồi thửa khô sâu nhất. Ngưỡng của mốc này được chọn trên seed phát triển (biến thể có tổng ngày khô quá ngưỡng và khô lúc trổ bông thấp nhất trong 18 biến thể).",
        "- Agent bản chỉnh: chỉ cộng biên an toàn 2 cm khi số đo đã cũ từ 1 ngày và thửa sắp vào giai đoạn cần giữ nước hoặc ruộng thoát nước kém khô lâu (còn lại biên 1 cm); xin đo lại khi số đo cũ 2 ngày chỉ nếu thửa có rủi ro, gom vào ngày trước lượt bơm; luôn xin khi cũ 3 ngày. Chỉnh trên seed 0–9, chạy seed kiểm tra một lần.",
        "- Lịch cố định là một mốc so sánh do nhóm tự dựng (luân phiên theo slot, tưới khi số đọc gần nhất ≤ −5 cm, ưu tiên thửa đang cần giữ nước), không phải quy trình đã khảo sát ở một HTX cụ thể.",
    ]
    (OUT / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
