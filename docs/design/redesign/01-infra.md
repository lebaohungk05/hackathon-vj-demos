# 01 · Hạ tầng Azure (INF)

Tổng: 18 giờ. Nhánh: `feat/inf-azure`. Làm đầu tiên vì mọi kế hoạch khác cần endpoint Azure OpenAI.

## Mục tiêu

Một lệnh tạo đủ hạ tầng cho cả dev và ngày thi, một lệnh xóa sạch sau cuộc thi. Không ai phải chép key bằng tay lên cloud.

## Thiết kế

```text
infra/
  main.bicep              Toàn bộ tài nguyên trong một resource group
  main.dev.bicepparam     Tham số: region, tên, model, capacity, email nhận cảnh báo
  deploy.ps1 / deploy.sh  Tạo resource group + chạy Bicep + in output
  dev-env.ps1 / .sh       Ghi .env cho máy dev (endpoint, tên deployment, key)
  teardown.ps1 / .sh      Xóa resource group
```

| Tài nguyên | Loại | Ghi chú |
| --- | --- | --- |
| Azure OpenAI | `Microsoft.CognitiveServices/accounts` (kind `OpenAI`) | `customSubDomainName` bắt buộc; `disableLocalAuth: false` vì dùng API key |
| Deployment `fast` | `.../accounts/deployments` | Model nhỏ, nhanh cho tin nhắn chữ, giọng nói, what-if |
| Deployment `strong` | `.../accounts/deployments` | Model có vision cho ảnh và ca xung đột |
| Log Analytics | `Microsoft.OperationalInsights/workspaces` | Bắt buộc cho Container Apps environment; giữ log 30 ngày |
| Container Apps environment | `Microsoft.App/managedEnvironments` | Gói Consumption |
| Container Registry | `Microsoft.ContainerRegistry/registries` (Basic) | `adminUserEnabled: false` |
| Managed identity | `Microsoft.ManagedIdentity/userAssignedIdentities` | Gán role AcrPull; dùng user-assigned để tránh lỗi kéo image lần đầu khi role chưa kịp gán |
| Budget | `Microsoft.Consumption/budgets` | Cảnh báo email ở 50 % / 80 % / 100 % |

Bản thân Container App được khai báo ở kế hoạch 06 (DEP-04), vì cần image trước.

## Task

| ID | Việc | File chính | Xong khi | Giờ | Phụ thuộc |
| --- | --- | --- | --- | --- | --- |
| INF-01 | Chọn region và model. Chạy `az cognitiveservices model list -l <region>` và kiểm tra quota cho Global Standard. Cần một model nhỏ (họ `gpt-4.1-mini` / `gpt-4o-mini` hoặc mới hơn) và một model có vision (họ `gpt-4.1` / `gpt-4o` hoặc mới hơn), cả hai hỗ trợ function calling và structured outputs. Ưu tiên region gần Việt Nam/Nhật nếu đủ quota | ADR 0004 mục "Model" | Có tên model, phiên bản, region, TPM ghi trong ADR | 2 | – |
| INF-02 | Khung Bicep: tham số, quy ước tên `rb-<env>-<loại>`, tag `project=ricebridge`, `env` | `infra/main.bicep`, `infra/main.dev.bicepparam` | `az bicep build` không lỗi | 2 | INF-01 |
| INF-03 | Azure OpenAI account + 2 deployment, `sku: GlobalStandard`; capacity theo model/version/region đã chọn, ghi rõ ánh xạ capacity → TPM/RPM. Đây là giới hạn tốc độ, không phải trần chi phí. Output endpoint/deployment/account | `infra/main.bicep` | Deploy xong; ADR ghi capacity và TPM/RPM thực tế của cả 2 deployment | 3 | INF-02 |
| INF-04 | Log Analytics, Container Apps environment, ACR Basic, user-assigned identity + role AcrPull trên ACR. Output: login server ACR, id identity, id environment | `infra/main.bicep` | Tạo xong; identity có AcrPull | 3 | INF-02 |
| INF-05 | Budget cảnh báo cho resource group, mặc định 50 USD/tháng, email lấy từ tham số; ghi rõ không tự dừng tài nguyên. Giới hạn token/request/live session do AGT-16 kiểm | `infra/main.bicep` | Budget hiển thị; runbook phân biệt cảnh báo chi phí và giới hạn ứng dụng | 1 | INF-02 |
| INF-06 | Script `deploy`, `dev-env`, `teardown` cho cả PowerShell và bash. `dev-env` lấy key bằng `az cognitiveservices account keys list` và ghi `.env` (không in key ra màn hình). `teardown` hỏi xác nhận trước khi xóa | `infra/*.ps1`, `infra/*.sh` | Chạy từ đầu đến cuối trên một subscription trống: tạo → ghi `.env` → xóa | 3 | INF-03, INF-04 |
| INF-07 | `.env.example` (không có giá trị thật) và hướng dẫn: cần `az` CLI, Bicep, quyền Contributor + User Access Administrator trên resource group (để gán AcrPull) | `.env.example`, `docs/manual/azure-setup.md` | Một thành viên khác làm theo tài liệu và có `.env` chạy được | 2 | INF-06 |
| INF-08 | Smoke fast với tin nhắn/tool giả và strong với ảnh; kiểm strict schema, tool_call id, response/refusal/filter và thời gian. Chốt OpenAI v1 hay AzureOpenAI/api_version theo model; cấu hình một lớp retry | `scripts/azure_smoke.py` | Cả 2 gọi thành công; ADR ghi API/model version, thời gian và TPM/RPM; script không in key | 2 | INF-06 |

## Rủi ro

| Rủi ro | Cách giảm |
| --- | --- |
| Region không còn quota cho model đã chọn | INF-01 kiểm tra trước; tham số hóa region và model để đổi nhanh |
| Không có quyền gán role trên subscription | Nhờ chủ subscription chạy INF-04 một lần; hoặc tạm dùng admin user của ACR (ghi rõ trong ADR 0005) |
| Chi phí phát sinh sau cuộc thi | Budget alert không tự ngắt; AGT-16 giới hạn lời gọi live, DEP-08 hướng dẫn dừng/xóa tài nguyên bằng INF-06 |

Tham khảo: [Azure quota](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/quota) mô tả capacity/TPM/RPM theo model; [Cost Management budgets](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets) chỉ cảnh báo, không dừng tiêu thụ.
