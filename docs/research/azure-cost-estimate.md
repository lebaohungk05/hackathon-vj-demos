# Ước tính chi phí Azure cho RiceBridge Ops

Ngày tính: 2026-10-14. Tất cả số tiền là **USD, giá niêm yết, trả theo mức dùng (pay-as-you-go), chưa có chiết khấu hợp đồng**. Subscription của Data Impact dùng gói Pay-As-You-Go nên giá niêm yết là giá thực tế.

Hai nguồn độc lập, kết quả khớp nhau:

1. **Azure Pricing Calculator**, điều khiển bằng Playwright ([scripts/azure_cost_estimate.py](../../scripts/azure_cost_estimate.py)). Máy tính không có API công khai nên script mở trang, điền form và đọc tổng.
2. **Azure Retail Prices API** (`https://prices.azure.com/api/retail/prices`, không cần đăng nhập) để đối chiếu đơn giá từng meter.

Các con số về **lượng token mỗi lần chạy** là **giả định** (mục 3), chưa đo. INF-07 (giao Nguyen Ngoc Hai) đo token thực, rồi INF-05 sửa bảng này.

## 1. Chi phí cố định hằng tháng (không phụ thuộc lượng dùng)

Vùng Southeast Asia cho Container Apps và Container Registry. Tính cho 31 ngày.

| Tài nguyên | Cấu hình | Cách tính | USD/tháng |
| --- | --- | --- | --- |
| Container Registry | Basic, 1 registry, ≤ 10 GiB đi kèm | 0,1666 USD/ngày × 31 (máy tính: 5,00 cho 30 ngày) | **5,00 – 5,16** |
| Container App | 0,5 vCPU / 1 GiB, Consumption, 1 replica chạy 24/7, **chủ yếu ở trạng thái rảnh** | vCPU rảnh 0,000004 USD/s + bộ nhớ 0,000004 USD/GiB·s, **không trừ** phần miễn phí (tính theo subscription, dùng chung với các app khác nên coi như hết) | **≈ 16** (16,07) |
| Container App, **cận trên** | Giả sử replica luôn bận cả tháng | vCPU bận 0,000034 USD/s; máy tính cho **48,96** (đã trừ phần miễn phí), không trừ thì ≈ 56 | ≤ 56 |
| Log Analytics | PerGB2018, giữ 30 ngày | Nạp log 2,99 USD/GB; 5 GB đầu mỗi tháng miễn phí; log của một Container App nhỏ ≪ 1 GB | **≈ 0** |
| Container Apps environment | Workload profile Consumption | Không có phí môi trường cho Consumption (`Environment Management Hour` chỉ áp dụng cho Dedicated) | 0 |
| Managed identity, resource group, budget | | Miễn phí | 0 |
| Azure OpenAI (hai deployment) | Global Standard | Không có phí chờ; chỉ tính theo token | 0 khi không gọi |
| **Cộng cố định** | | | **≈ 21 (cận dưới) đến ≈ 61 (cận trên)** |

Lưu ý: máy tính Container Apps chỉ mô hình hóa thời gian **bận** (số request × thời gian xử lý). Không có ô nào cho replica rảnh chạy liên tục, nên con số "≈ 16" phải tính tay từ đơn giá Retail API; hai trường hợp 0,00 và 48,96 của máy tính là hai đầu của khoảng, không phải ước tính thực tế.

## 2. Đơn giá token (Global Standard, USD cho 1 triệu token)

Đối chiếu bằng Retail API; **giá Global giống nhau ở mọi vùng**.

| Model | Input | Input được cache | Output | Vòng đời ở japaneast |
| --- | --- | --- | --- | --- |
| `gpt-6-luna` | 0,10 | 0,01 | 0,50 | GA, hết hỗ trợ 2028-03-11 |
| `gpt-5.6-luna` | 0,20 | 0,02 | 1,20 | GA, 2028-01-11 |
| `gpt-5.4-mini` | 0,75 | 0,075 | 4,50 | GA, 2027-09-21 |
| `gpt-4.1-mini` | 0,40 | 0,10 | 1,60 | **Legacy**, 2027-04-14 |
| `gpt-6-sol` / `gpt-6.1-sol` | 2,00 | 0,20 / 0,10 | 10,00 | GA, 2028-03-11 |
| `gpt-5.6-terra` | 2,00 | 0,20 | 12,00 | GA, 2028-01-11 |
| `gpt-5.4` | 2,50 | 0,25 | 15,00 | GA, 2027-09-02 |
| `gpt-5.5` | 5,00 | 0,50 | 30,00 | GA, 2027-10-26 |

Hai điều nên đọc ra từ bảng:

- Họ `gpt-4.1` mà bản kế hoạch gốc gợi ý nay đã ở trạng thái **Legacy** (hết hỗ trợ sớm hơn các họ mới khoảng 5–11 tháng) và không rẻ hơn họ `gpt-6` nhỏ (`gpt-6-luna` rẻ hơn khoảng 4 lần ở input, 3 lần ở output).
- Cache input chỉ tính 10 % giá input thường. Prompt hệ thống và định nghĩa công cụ của agent lặp lại ở mỗi vòng, nên cache là đòn bẩy chi phí lớn nhất.

Ba điều **chưa kiểm chứng** về model: vision, function calling và structured outputs của từng model (CLI không cho cờ), độ chính xác đọc thước, và độ trễ. Việc kiểm là INF-07, giao Nguyen Ngoc Hai.

## 3. Giả định về lượng dùng

Căn cứ vào thiết kế agent ([03](../design/redesign/03-agent-loop.md)): tối đa 8 lần chạy công cụ mỗi lượt, mỗi lượt gọi LLM nhiều vòng và prompt gồm hướng dẫn hệ thống, mô tả 11 công cụ, kết quả công cụ.

| Kịch bản | Số lượt chạy cả đợt | Input mỗi lượt | Output mỗi lượt |
| --- | --- | --- | --- |
| Thấp | 2.000 | 18.000 token | 1.000 token |
| **Cơ sở** | **6.000** | **36.000 token** | **1.500 token** |
| Cao | 12.000 | 60.000 token | 2.500 token |

- 70 % lượt dùng deployment `fast`, 30 % dùng `strong` (ảnh, ca xung đột); lượt `strong` có output nhiều hơn khoảng 1,3 lần.
- "Cả đợt" gồm phát triển, chạy bộ đánh giá ≥ 30 ca ngoài kịch bản nhiều lần, diễn tập và các buổi demo. Không phải một tháng thuần phát triển.
- Chưa tính cache. Dòng "cache 50 %" giả định một nửa input rơi vào cache.

## 4. Chi phí token theo cặp model

Cặp **A** = `fast: gpt-6-luna` + `strong: gpt-6-sol`. Cặp **B** = `fast: gpt-5.4-mini` + `strong: gpt-5.4`.

Kịch bản **Cơ sở**, **số liệu của máy tính Playwright** (đối chiếu tay: khớp từng đồng):

| Deployment | Input (nghìn token) | Output (nghìn token) | USD |
| --- | --- | --- | --- |
| A · fast `gpt-6-luna` | 151.200 | 6.300 | 18,27 |
| A · strong `gpt-6-sol` | 64.800 | 3.600 | 165,60 |
| **Cặp A, cộng** | | | **183,87** |
| B · fast `gpt-5.4-mini` | 151.200 | 6.300 | 141,75 |
| B · strong `gpt-5.4` | 64.800 | 3.600 | 216,00 |
| **Cặp B, cộng** | | | **357,75** |

Cả ba kịch bản (tính tay từ đơn giá Retail API, có kèm trường hợp cache một nửa input):

| Kịch bản | Cặp A | Cặp A, cache 50 % | Cặp B | Cặp B, cache 50 % |
| --- | --- | --- | --- | --- |
| Thấp (2.000 lượt) | 32,6 | 21,8 | 63,9 | 43,3 |
| Cơ sở (6.000 lượt) | 183,0 | 117,9 | 356,4 | 232,5 |
| Cao (12.000 lượt) | 609,9 | 392,8 | 1.188,0 | 774,9 |

(Hai số "Cơ sở" của cặp A và B chênh khoảng 1 USD so với bảng máy tính phía trên vì cách làm tròn số token output của lượt `strong`.)

## 5. Tổng chi phí đợt thi và ý nghĩa với budget

| Kịch bản | Cố định (≈ 21–61) + token cặp A | Cố định + token cặp B |
| --- | --- | --- |
| Thấp | ≈ 54 – 94 | ≈ 85 – 125 |
| **Cơ sở** | **≈ 205 – 245** | **≈ 379 – 419** |
| Cao | ≈ 631 – 671 | ≈ 1.209 – 1.249 |

Kết luận:

- Bản kế hoạch gốc đặt budget mặc định **50 USD/tháng**. Với kịch bản Cơ sở và cặp A, mức đó bị vượt trong khoảng một tuần. Cần đặt budget theo phép tính này, kèm cảnh báo dự báo (forecast), và **đo token thực ở INF-07 để thay số giả định**.
- Chọn model là quyết định chi phí lớn nhất: cặp B đắt gấp khoảng 2 lần cặp A cho cùng khối lượng.
- Chi phí hạ tầng cố định nhỏ so với token. Rủi ro tiền chủ yếu nằm ở số lượt chạy `strong`, không ở Container Apps hay ACR.
- Khi hạn mức tiêu thụ cần chặn cứng, phải làm ở ứng dụng (AGT-16: token và số request mỗi lượt/phiên). Budget Azure chỉ cảnh báo.

### 5.1 Phương án giới hạn 30 USD (quyết định của chủ dự án)

Chủ dự án quyết định **chi thực tế không quá 30 USD** cho 26 ngày (14/10 – 09/11/2026) và ghi 30 USD trong ticket. Các kịch bản ở mục 4–5 (6.000 lượt trở lên) vượt xa mức này, nên phải giảm số lượt chạy:

| Phương án | Container App | Cố định | Ngân sách token | Số lượt chạy |
| --- | --- | --- | --- | --- |
| **A** (mặc định) | luôn bật, 1 replica rảnh 26 ngày: 13,5 | 4,33 + 13,5 = **17,8** | **12,2** | khoảng **2.800** (toàn `gpt-6-luna`) |
| **B** | như A | 17,8 | 12,2 | khoảng **1.400** (95 % `gpt-6-luna`, 5 % `gpt-6-sol`) |
| **C** | tắt về 0 khi không dev/test, bật ~4 ngày: 7,3 | 4,33 + 7,3 = **11,6** | **18,4** | khoảng **2.100** (95 % luna, 5 % sol) |

Đơn giá mỗi lượt (36.000 token vào, 1.500 ra): `gpt-6-luna` ≈ 0,0043 USD, `gpt-6-sol` ≈ 0,091 USD (lượt `strong` ra nhiều token hơn khoảng 1,3 lần). Container App rảnh: 0,000004 USD/s cho mỗi vCPU và mỗi GiB; bận: 0,000034 USD/s/vCPU.

File Excel đính kèm ticket mô tả **phương án A**: Container Registry 4,33 + Container Apps 13,48 + Azure OpenAI 12,18 (khoảng 2.800 lượt `gpt-6-luna`) = **29,99 USD**. Máy tính không có mô hình replica rảnh, nên dòng Container Apps được đặt bằng số giây "bận" tương đương để ra gần đúng 13,48 USD (sau phần miễn phí mà máy tính tự trừ). Tạo lại bằng:

```bash
python scripts/azure_cost_estimate.py --days 26 --export outputs/azure-cost/ExportedEstimate.xlsx
```

Hệ quả: **số lượt chạy cả đợt chỉ khoảng 1.400 – 2.800**; giới hạn token cả đợt phải đặt trong ứng dụng (AGT-16), vì budget Azure chỉ cảnh báo.

## 6. Hạn chế của ước tính

- Giá niêm yết ngày 2026-10-14; giá và danh sách model thay đổi.
- Chưa tính: băng thông đi ra (rất nhỏ với JSON và ảnh JPEG vài trăm KB), thuế, chênh lệch tỷ giá, dung lượng ACR vượt 10 GiB.
- Số token mỗi lượt là giả định. Ảnh đưa vào vision tốn thêm token đầu vào (chưa đo).
- Không tính nhân công, hay chi phí gói hỗ trợ (dùng gói Basic đi kèm).
- Máy tính Azure thay đổi giao diện theo thời gian; script báo `failed` thay vì trả số sai nếu không điền được ô nào.

## 7. Đã kiểm chứng với tài liệu Microsoft

- Phần miễn phí Container Apps (180.000 vCPU·giây, 360.000 GiB·giây, 2 triệu request mỗi tháng) tính **theo subscription**; replica rảnh khi dưới 0,01 vCPU và 1.000 byte/giây mạng, không xử lý HTTP; Consumption không có phí quản lý môi trường ([Billing in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/billing)).
- Azure OpenAI xóa mềm 48 giờ ([Recover or purge deleted resources](https://learn.microsoft.com/en-us/azure/ai-services/recover-purge-resources)).
- Tổng của máy tính khi gộp bốn dòng (ACR, Container Apps luôn bận, `gpt-6-luna`, `gpt-6-sol`) là **237,83 USD** và khớp tổng từng dòng (5,00 + 48,96 + 18,27 + 165,60).

## 8. Tái hiện

```bash
python -m pip install -e ".[test]" && python -m playwright install chromium
python scripts/azure_cost_estimate.py --shots outputs/azure-cost          # toàn bộ kịch bản
python scripts/azure_cost_estimate.py --only aoai_fast                    # một nhóm
python scripts/azure_cost_estimate.py --export outputs/azure-cost/ExportedEstimate.xlsx   # một estimate cho cả hệ thống + file Excel của máy tính
```

Đối chiếu đơn giá bằng Retail API, ví dụ cho Container Apps ở Southeast Asia:
`https://prices.azure.com/api/retail/prices?$filter=serviceName eq 'Azure Container Apps' and armRegionName eq 'southeastasia'`.
