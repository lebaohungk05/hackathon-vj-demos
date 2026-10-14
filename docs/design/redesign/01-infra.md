# 01 · Hạ tầng Azure (INF)

Tổng: 6 giờ (chưa tính INF-07). Phạm vi: hạ tầng Azure. Việc kiểm năng lực model và đo token (mục 7, INF-07) không thuộc hạ tầng, giao Nguyen Ngoc Hai review và làm.

## 1. Mục tiêu

Dựng đủ hạ tầng để dev và test, tạo bằng tay theo [hướng dẫn từng bước](../../manual/azure-create-resources.md). Chi phí thực tế tối đa 30 USD (xin 50 USD) cho giai đoạn 14/10 – 09/11/2026. Khi không dùng thì tắt; chỉ xóa khi chắc chắn không dùng nữa.

## 2. Đặt tên và tag

| Tài nguyên | Tên |
| --- | --- |
| Resource group | `di-hackathon-ricebridge` (vùng `southeastasia`) |
| Azure OpenAI account | `dev-oai-ricebridge-001` (custom domain trùng tên) |
| Deployment | `fast`, `strong` |
| Log Analytics workspace | `dev-law-ricebridge-001` |
| Container Apps environment | `dev-cae-ricebridge-001` |
| Container Registry | `devcrricebridge001` |
| Managed identity | `dev-mi-ricebridge-001` |
| Container App (kế hoạch 06, DEP-04) | `dev-ca-ricebridge-001` |
| Budget | `Monthly_Budget_ricebridge_30USD` |

| Tag | Giá trị |
| --- | --- |
| `Environment` | `dev` |
| `Project` | `ricebridge` |
| `ManagedBy` | `Manual` |
| `Group` | `Spark` |
| `Owner` | `Vu Truong Thinh` |

Gắn tag trên resource group và trên từng tài nguyên.

## 3. Tài nguyên

Vùng: Azure OpenAI ở `japaneast`, còn lại ở `southeastasia`.

| Tài nguyên | Loại | SKU / gói | Thiết lập |
| --- | --- | --- | --- |
| Resource group | `Microsoft.Resources/resourceGroups` | – | Tag mục 2 |
| Azure OpenAI account | `Microsoft.CognitiveServices/accounts`, kind `OpenAI` | `S0` | Custom domain; dùng API key; mạng công khai |
| Deployment `fast`, `strong` | `.../accounts/deployments` | `GlobalStandard` | Model ở mục 7; tắt tự nâng cấp phiên bản; filter `Microsoft.DefaultV2`; capacity ở mục 4 |
| Log Analytics | `Microsoft.OperationalInsights/workspaces` | `PerGB2018` | Giữ 30 ngày; trần 1 GB/ngày |
| Container Apps environment | `Microsoft.App/managedEnvironments` | workload profile `Consumption` | Log về workspace trên; không zone redundant |
| Container Registry | `Microsoft.ContainerRegistry/registries` | `Basic` | Tắt admin user |
| Managed identity | `Microsoft.ManagedIdentity/userAssignedIdentities` | – | Role `AcrPull` trên registry |
| Budget | Cost Management | – | Mục 5 |
| Container App | `Microsoft.App/containerApps` | Consumption | Tạo ở kế hoạch 06 (DEP-04): 0,5 vCPU, 1 GiB, 1 replica |

## 4. Capacity

1 đơn vị capacity ≈ 1.000 token/phút và 1 request/phút.

| Deployment | Capacity | Tương đương |
| --- | --- | --- |
| `fast` | 150 | 150.000 TPM, 150 RPM |
| `strong` | 100 | 100.000 TPM, 100 RPM |

## 5. Chi phí

| Khoản | USD |
| --- | --- |
| Xin trong ticket | 50 |
| Giới hạn thực tế (budget cảnh báo) | 30 |
| Dự phòng | 20 |

Phương án cho 26 ngày:

| Phương án | Cố định | Ngân sách token | Số lượt chạy |
| --- | --- | --- | --- |
| **A** (mặc định): Container App luôn bật (`min-replicas 1`); mọi lượt dùng `fast` (`gpt-6-luna`) | 17,8 | 12,2 | khoảng 2.800 |
| **B**: như A, 5% lượt dùng `strong` (`gpt-6-sol`) | 17,8 | 12,2 | khoảng 1.400 |
| **C**: Container App về 0 khi không dev/test (`min-replicas 0`), bật khoảng 4 ngày; 5% lượt `strong` | 11,6 | 18,4 | khoảng 2.100 |

Budget tạo trên Portal, phạm vi resource group, 30 USD/tháng. Cảnh báo: Actual 50 %, 80 %, 100 %, 150 %; Forecasted 100 %. Chỉ cảnh báo, không dừng tài nguyên.

Người nhận (mọi ngưỡng, gửi bằng email từ Azure Cost Management):

- `nguyen.ngoc.bach@dataimpact.vn`
- `le.bao.hung@dataimpact.vn`
- `nguyen.ngoc.hai@dataimpact.vn`

Chi tiết tính toán ở [azure-cost-estimate.md](../../research/azure-cost-estimate.md).

## 6. Task

| ID | Việc | File chính | Xong khi | Giờ | Phụ thuộc |
| --- | --- | --- | --- | --- | --- |
| INF-01 | Chốt region và model: OpenAI `japaneast`, còn lại `southeastasia`; cặp model tạm `gpt-6-luna` + `gpt-6-sol` (mục 7) | ADR 0004 mục "Model" | Có cặp model kèm giá và ngày hết hỗ trợ | 1 | – |
| INF-02 | Tạo tài nguyên theo [hướng dẫn](../../manual/azure-create-resources.md): resource group, Log Analytics, ACR, identity + AcrPull, Container Apps environment, Azure OpenAI, hai deployment; tắt tự nâng cấp phiên bản trên Portal | – | `az resource list` đủ tài nguyên và 2 deployment; admin ACR tắt; capacity 150 và 100 | 1,5 | INF-01 |
| INF-03 | Tạo budget 30 USD trên Portal, gửi cảnh báo qua email tới 3 người nhận ở mục 5 | – | Budget hiển thị đúng phạm vi và ngưỡng | 0,5 | INF-02 |
| INF-04 | `.env.example`, ghi `.env` từ endpoint và key (không in key, không commit), smoke test hạ tầng: mỗi deployment trả lời một lời gọi tối thiểu; rate limit khớp capacity | `.env.example`, `scripts/azure_smoke.py` | Cả 2 deployment trả lời; script không in key | 2 | INF-02 |
| INF-05 | Sau khoảng 1 tuần dùng, đối chiếu chi phí thực trong Cost Management và số token do INF-07 đo với giới hạn 30 USD; chỉnh phương án hoặc budget nếu lệch | `docs/research/azure-cost-estimate.md` | Có số chi phí thực | 1 | INF-04, INF-07 |
| INF-06 | Tắt: Container App `--min-replicas 0`. Xóa (chỉ khi chắc chắn không dùng nữa): xóa resource group, purge account OpenAI, kiểm không còn resource group `ME_*` | – | Tắt: 0 replica. Xóa: không còn tài nguyên | 0 (làm khi cần) | – |
| INF-07 | **Không thuộc hạ tầng; giao Nguyen Ngoc Hai review và làm.** Smoke test mọi model ứng viên: `fast` với tin nhắn/tool giả, `strong` với ảnh thước; kiểm vision, function calling, structured outputs, tool_call id, response/refusal/filter, thời gian; đo token mỗi lượt; chốt OpenAI v1 hay AzureOpenAI/api_version, một lớp retry | `scripts/azure_model_check.py` | Mỗi ứng viên có kết quả và thời gian; ADR ghi model/API version, TPM/RPM, token/lượt | 3 (không tính vào 6) | INF-04 |

## 7. Ma trận chọn model (Nguyen Ngoc Hai review và làm)

Giá USD/1M token, Global Standard, `japaneast`, 2026-10-14. Ba cột cuối do INF-07 điền.

| Ứng viên | Vai trò | Input / output | Hết hỗ trợ | Vision | Function calling | Structured outputs |
| --- | --- | --- | --- | --- | --- | --- |
| `gpt-6-luna` | fast (chọn tạm) | 0,10 / 0,50 | 2028-03-11 | ? | ? | ? |
| `gpt-5.4-mini` | fast | 0,75 / 4,50 | 2027-09-21 | ? | ? | ? |
| `gpt-6-sol` hoặc `gpt-6.1-sol` | strong (chọn tạm) | 2,00 / 10,00 | 2028-03-11 | ? | ? | ? |
| `gpt-5.4` | strong | 2,50 / 15,00 | 2027-09-02 | ? | ? | ? |
| `gpt-4.1-mini`, `gpt-4.1` | fast, strong | 0,40 / 1,60 cho mini | Legacy, 2027-04-14 | ? | ? | ? |

## 8. Rủi ro

Biến `SUB`, `RG`, `ACR_ID` như trong [hướng dẫn tạo tay](../../manual/azure-create-resources.md).

| Rủi ro | Phòng | Xử lý nếu đã xảy ra |
| --- | --- | --- |
| Tạo nhầm vào subscription khác (máy có nhiều tài khoản Azure, mặc định có thể là subscription cá nhân) | Mọi lệnh có `--subscription "$SUB"`; chạy bước 1 của mục 9 trước khi tạo | Mục 10, dòng 2 |
| Tạo vào resource group khác (ví dụ resource group của dự án khác) | Chỉ dùng biến `$RG`, không gõ tên tay; trước khi tạo, `az group show` phải thấy `Project=ricebridge`; không tạo vào resource group có sẵn của dự án khác | Mục 10, dòng 3. Không bao giờ xóa resource group không phải của mình |
| Tạo sai tên, vùng hoặc SKU | Đối chiếu bảng mục 2 và 3 trước mỗi lệnh | Tên, vùng, SKU không đổi được: xóa tài nguyên đó và tạo lại (mục 10, dòng 1) |
| Tạo thừa hoặc trùng tài nguyên | Chạy từng bước và verify sau mỗi bước | Mục 9, bước 3 liệt kê phần thừa; xóa phần thừa (mục 10, dòng 1) |
| Sai thiết lập (bật admin ACR, quên tắt tự nâng cấp phiên bản, sai capacity) | Mục 9, bước 6, 7, 11 | Mục 10, dòng 4 |
| Thiếu hoặc sai tag | Truyền `--tags` cho mọi lệnh tạo; mục 9, bước 5 | Mục 10, dòng 4 |
| Lộ key | Key chỉ vào `.env` và secret của Container App; không chép vào chat, ticket hay file được commit | Mục 10, dòng 5 |
| Hết quota model đã chọn | Đổi region hoặc model: xóa và tạo lại deployment cùng tên | Mục 10, dòng 1 |
| Thiếu quyền gán role hoặc purge | Người tạo cần Contributor và User Access Administrator ở phạm vi subscription | Nhờ chủ subscription cấp quyền rồi chạy lại bước bị lỗi |
| Vượt 30 USD | Budget Actual + Forecasted; 20 USD dự phòng; phương án C; giới hạn số lượt ở phía ứng dụng | Mục 10, dòng 6 |
| Chi phí khi không dùng | Tắt Container App về 0; ACR Basic vẫn tốn khoảng 5 USD/tháng nếu chưa xóa | Mục 10, dòng 6 và 7 |

## 9. Verify

Chạy sau khi tạo xong (bước 1 và 2 chạy cả trước khi tạo). Ngoài ra chạy bước tương ứng ngay sau mỗi bước tạo.

| # | Kiểm tra | Lệnh | Kết quả đúng |
| --- | --- | --- | --- |
| 1 | Subscription | `az account show --subscription "$SUB" --query "{name:name,state:state}" -o table` | Đúng subscription của Data Impact, `Enabled` |
| 2 | Resource group | `az group show --subscription "$SUB" -n $RG --query "{loc:location,tags:tags}" -o json` | `southeastasia`; đủ 5 tag mục 2 |
| 3 | Danh sách tài nguyên | `az resource list --subscription "$SUB" -g $RG --query "[].name" -o tsv` | Đúng 5 tên: `dev-law-ricebridge-001`, `devcrricebridge001`, `dev-mi-ricebridge-001`, `dev-cae-ricebridge-001`, `dev-oai-ricebridge-001` (thêm `dev-ca-ricebridge-001` sau DEP-04); không có tên khác |
| 4 | Không tạo nhầm chỗ khác | `az resource list --subscription "$SUB" --query "[?contains(name,'ricebridge')].{name:name,rg:resourceGroup}" -o table` | Mọi dòng thuộc `di-hackathon-ricebridge` |
| 5 | Tag | `az resource list --subscription "$SUB" -g $RG --query "[?tags.Project!='ricebridge' \|\| tags.Environment!='dev' \|\| tags.ManagedBy!='Manual'].name" -o tsv` | Rỗng |
| 6 | Container Registry | `az acr show --subscription "$SUB" -g $RG -n devcrricebridge001 --query "{sku:sku.name,admin:adminUserEnabled}" -o table` | `Basic`, `False` |
| 7 | Quyền kéo image | `az role assignment list --subscription "$SUB" --scope "$ACR_ID" --query "[].{role:roleDefinitionName,principal:principalId}" -o table` | Một dòng `AcrPull`, `principal` là id của `dev-mi-ricebridge-001` |
| 8 | Log Analytics | `az monitor log-analytics workspace show --subscription "$SUB" -g $RG -n dev-law-ricebridge-001 --query "{sku:sku.name,days:retentionInDays,quotaGb:workspaceCapping.dailyQuotaGb}" -o table` | `PerGB2018`, 30, 1 |
| 9 | Container Apps environment | `az containerapp env show --subscription "$SUB" -g $RG -n dev-cae-ricebridge-001 --query "{loc:location,profiles:properties.workloadProfiles[].workloadProfileType}" -o json` | `southeastasia`, `Consumption` |
| 10 | Azure OpenAI account | `az cognitiveservices account show --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 --query "{kind:kind,sku:sku.name,loc:location,domain:properties.customSubDomainName,public:properties.publicNetworkAccess}" -o table` | `OpenAI`, `S0`, `japaneast`, `dev-oai-ricebridge-001`, `Enabled` |
| 11 | Deployment | `az cognitiveservices account deployment list --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 --query "[].{name:name,model:properties.model.name,sku:sku.name,cap:sku.capacity,upgrade:properties.versionUpgradeOption}" -o table` | `fast`: `gpt-6-luna`, `GlobalStandard`, 150, `NoAutoUpgrade`; `strong`: `gpt-6-sol`, `GlobalStandard`, 100, `NoAutoUpgrade` |
| 12 | Budget | Portal: Cost Management → Budgets | `Monthly_Budget_ricebridge_30USD`, 30 USD, phạm vi resource group, 5 cảnh báo, 3 người nhận |
| 13 | Smoke test | INF-04 | Cả 2 deployment trả lời |
| 14 | Chi phí | Portal: Cost analysis, lọc resource group | Sau 1–2 ngày, chi phí khớp phương án đã chọn; không có dòng chi phí ngoài danh sách bước 3 |

## 10. Rollback

| # | Tình huống | Cách làm | Xác nhận |
| --- | --- | --- | --- |
| 1 | Tạo sai hoặc thừa một tài nguyên | `az resource delete --subscription "$SUB" --ids <id>`; với Azure OpenAI chạy thêm `az cognitiveservices account purge --subscription "$SUB" -g $RG -n <tên> -l <vùng>`; rồi tạo lại đúng | Mục 9, bước 3 |
| 2 | Tạo nhầm vào subscription khác | Lặp dòng 1 cho từng tài nguyên `ricebridge` với `--subscription` của subscription sai | `az resource list --subscription <sai> --query "[?contains(name,'ricebridge')]"` rỗng |
| 3 | Tạo nhầm vào resource group khác | Lấy danh sách bằng mục 9, bước 4; xóa từng tài nguyên thuộc resource group không phải `di-hackathon-ricebridge` bằng dòng 1; **không** chạy `az group delete` trên resource group không phải của mình | Mục 9, bước 4 chỉ còn dòng của `di-hackathon-ricebridge` |
| 4 | Sai thiết lập tại chỗ | ACR: `az acr update --subscription "$SUB" -g $RG -n devcrricebridge001 --admin-enabled false`. Tag: `az tag update --resource-id <id> --operation Merge --tags <key>=<value>`. Tự nâng cấp hoặc capacity: sửa trên Portal (Deployments), hoặc `az cognitiveservices account deployment delete --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 --deployment-name <fast hoặc strong>` rồi tạo lại | Mục 9, bước tương ứng |
| 5 | Lộ key | `az cognitiveservices account keys regenerate --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 --key-name Key1`; cập nhật `.env` và secret `aoai-key` của Container App | Key cũ bị từ chối; smoke test (INF-04) chạy lại thành công |
| 6 | Tắt, không xóa | `az containerapp update --subscription "$SUB" -g $RG -n dev-ca-ricebridge-001 --min-replicas 0` | Container App về 0 replica |
| 7 | Xóa toàn bộ (chỉ khi chắc chắn không dùng nữa) | `az group delete --subscription "$SUB" -n $RG --yes --no-wait`; đợi xóa xong; `az cognitiveservices account purge --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 -l <vùng>`; xóa budget trên Portal nếu còn | `az group exists --subscription "$SUB" -n $RG` là `false`; `az cognitiveservices account list-deleted --subscription "$SUB" --query "[?contains(name,'ricebridge')]"` rỗng; không còn resource group `ME_dev-cae-ricebridge-001_*` |
