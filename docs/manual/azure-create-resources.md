# Tạo tài nguyên Azure cho RiceBridge Ops bằng tay

Hướng dẫn từng bước để tạo hạ tầng bằng Azure CLI (hoặc làm theo cùng thông số trên Portal). Không cần lưu state. Thiết kế và lý do từng lựa chọn nằm ở [01 · Hạ tầng Azure](../design/redesign/01-infra.md); chi phí ở [ước tính chi phí](../research/azure-cost-estimate.md).

## Trước khi làm

- Phiếu xin tài nguyên đã được người duyệt đồng ý.
- Đã cài Azure CLI 2.81 trở lên và `az login`.
- Người tạo có quyền Contributor và User Access Administrator ở phạm vi **subscription** (cần để gán role AcrPull và để purge Azure OpenAI sau này).
- Mọi lệnh dùng `--subscription` rõ ràng, không dựa vào subscription mặc định của máy (máy có thể đang trỏ tới subscription cá nhân).

## Danh sách tài nguyên

| # | Tài nguyên | Tên | Vùng | Gói | Thiết lập chính |
| --- | --- | --- | --- | --- | --- |
| 1 | Resource group | `di-hackathon-ricebridge` | `southeastasia` | – | Tag mục dưới |
| 2 | Log Analytics workspace | `dev-law-ricebridge-001` | `southeastasia` | `PerGB2018` | Giữ 30 ngày; trần 1 GB/ngày |
| 3 | Container Registry | `devcrricebridge001` | `southeastasia` | `Basic` | Tắt admin user |
| 4 | Managed identity | `dev-mi-ricebridge-001` | `southeastasia` | – | Role `AcrPull` trên registry |
| 5 | Container Apps environment | `dev-cae-ricebridge-001` | `southeastasia` | Consumption | Log về workspace ở dòng 2 |
| 6 | Azure OpenAI account | `dev-oai-ricebridge-001` | `japaneast` | `S0` | Custom domain trùng tên; dùng API key; mạng công khai |
| 7 | Deployment `fast` | – | – | `GlobalStandard` | `gpt-6-luna`, capacity 150 |
| 8 | Deployment `strong` | – | – | `GlobalStandard` | `gpt-6-sol`, capacity 100 |
| 9 | Budget | `Monthly_Budget_ricebridge_30USD` | – | – | Tạo trên Portal (xem mục Budget) |
| 10 | Container App `dev-ca-ricebridge-001` | Tạo sau, khi đã có image (kế hoạch 06, DEP-04) | `southeastasia` | Consumption | 0,5 vCPU, 1 GiB, 1 replica |

**Tag** gắn cho mọi tài nguyên: `Environment=dev`, `Project=ricebridge`, `ManagedBy=Manual`, `Group=Spark`, `Owner=Vu Truong Thinh`. Azure không tự kế thừa tag từ resource group, nên mỗi lệnh tạo bên dưới đều truyền `--tags` (deployment, role assignment và budget không gắn tag được). Các tag `Department`, `Group`, `Owner`, `CostCenter` không bắt buộc.

Hai tên duy nhất toàn cầu (`devcrricebridge001`, `dev-oai-ricebridge-001`) đã kiểm tra ngày 14/10/2026: còn trống.

## Các bước

Mở PowerShell hoặc bash. Ví dụ dưới là bash (`TAGS` là mảng vì giá trị `Owner` có dấu cách). Trên PowerShell đổi `VAR=...` thành `$VAR = "..."`, dùng dấu ` ở cuối dòng thay cho `\` để xuống dòng, khai báo `$TAGS = @("Environment=dev","Project=ricebridge","ManagedBy=Manual","Group=Spark","Owner=Vu Truong Thinh")` và truyền `--tags $TAGS`.

```bash
SUB="<tên hoặc mã subscription>"
RG=di-hackathon-ricebridge
TAGS=(Environment=dev Project=ricebridge ManagedBy=Manual Group=Spark "Owner=Vu Truong Thinh")
```

**1. Resource group**

```bash
az group create --subscription "$SUB" -n $RG -l southeastasia --tags "${TAGS[@]}"
```

**2. Log Analytics** (giữ 30 ngày, trần 1 GB/ngày để log không tốn tiền bất ngờ)

```bash
az monitor log-analytics workspace create --subscription "$SUB" -g $RG -n dev-law-ricebridge-001 \
  -l southeastasia --sku PerGB2018 --retention-time 30 --quota 1 --tags "${TAGS[@]}"
```

**3. Container Registry** (tắt admin user; image kéo bằng identity)

```bash
az acr create --subscription "$SUB" -g $RG -n devcrricebridge001 -l southeastasia \
  --sku Basic --admin-enabled false --tags "${TAGS[@]}"
```

**4. Managed identity và quyền kéo image**

```bash
az identity create --subscription "$SUB" -g $RG -n dev-mi-ricebridge-001 -l southeastasia --tags "${TAGS[@]}"

PRINCIPAL=$(az identity show --subscription "$SUB" -g $RG -n dev-mi-ricebridge-001 --query principalId -o tsv)
ACR_ID=$(az acr show --subscription "$SUB" -g $RG -n devcrricebridge001 --query id -o tsv)
az role assignment create --subscription "$SUB" --assignee-object-id "$PRINCIPAL" \
  --assignee-principal-type ServicePrincipal --role AcrPull --scope "$ACR_ID"
```

Nếu lệnh gán role báo `PrincipalNotFound`, đợi vài chục giây cho identity mới tạo lan truyền rồi chạy lại.

**5. Container Apps environment** (khóa workspace chỉ nằm trong biến, không in ra)

```bash
WS_ID=$(az monitor log-analytics workspace show --subscription "$SUB" -g $RG -n dev-law-ricebridge-001 --query customerId -o tsv)
WS_KEY=$(az monitor log-analytics workspace get-shared-keys --subscription "$SUB" -g $RG -n dev-law-ricebridge-001 --query primarySharedKey -o tsv)
az containerapp env create --subscription "$SUB" -g $RG -n dev-cae-ricebridge-001 -l southeastasia \
  --logs-workspace-id "$WS_ID" --logs-workspace-key "$WS_KEY" --enable-workload-profiles true --tags "${TAGS[@]}"
```

**6. Azure OpenAI account**

```bash
az cognitiveservices account create --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 \
  -l japaneast --kind OpenAI --sku S0 --custom-domain dev-oai-ricebridge-001 --tags "${TAGS[@]}" --yes
```

**7 và 8. Hai deployment** (đặt tên theo vai trò, không theo tên model)

```bash
az cognitiveservices account deployment create --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 \
  --deployment-name fast --model-format OpenAI --model-name gpt-6-luna --model-version 2026-09-22 \
  --sku-name GlobalStandard --sku-capacity 150

az cognitiveservices account deployment create --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 \
  --deployment-name strong --model-format OpenAI --model-name gpt-6-sol --model-version 2026-09-22 \
  --sku-name GlobalStandard --sku-capacity 100
```

Hai bản model trên đọc từ `az cognitiveservices model list -l japaneast` ngày 2026-10-14; nếu lệnh báo sai phiên bản thì chạy lệnh đó để lấy bản hiện hành. Capacity 150 và 100 tương đương khoảng 150.000 và 100.000 token/phút (1 đơn vị ≈ 1.000 token/phút).

Sau khi tạo, vào Portal (Azure OpenAI account → Deployments → từng deployment) và đặt **Automatic model version upgrade = Disabled**, để model đứng yên suốt cuộc thi. Lệnh `az` ở trên không có tùy chọn này.

**9. Budget** (Portal)

Cost Management → Budgets → Add, phạm vi là resource group `di-hackathon-ricebridge`:

| Trường | Giá trị |
| --- | --- |
| Name | `Monthly_Budget_ricebridge_30USD` |
| Reset period | Monthly |
| Creation date | ngày 1 của tháng hiện tại (01/10/2026) |
| Expiration date | 30/11/2026 |
| Amount | 30 |
| Alert 1 | Actual, 50 % |
| Alert 2 | Actual, 80 % |
| Alert 3 | Actual, 100 % |
| Alert 4 | Actual, 150 % (= 45 USD, gần hết phần dự phòng 50 USD) |
| Alert 5 | Forecasted, 100 % |
| Alert recipients (cả 5 cảnh báo) | `nguyen.ngoc.bach@dataimpact.vn`, `le.bao.hung@dataimpact.vn`, `nguyen.ngoc.hai@dataimpact.vn` |

Budget chỉ **cảnh báo, không dừng tài nguyên**. Giới hạn thật nằm ở ứng dụng (số lượt gọi và token).

## Container App (sau khi đã có image)

Làm ở kế hoạch 06 (DEP-04), khi image đã được đẩy lên registry (`az acr build -t ricebridge:<git-sha> ...`). Container App kéo image bằng managed identity ở bước 4, nên không cần mật khẩu registry:

```bash
MI_ID=$(az identity show --subscription "$SUB" -g $RG -n dev-mi-ricebridge-001 --query id -o tsv)
AOAI_KEY=$(az cognitiveservices account keys list --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 --query key1 -o tsv)

az containerapp create --subscription "$SUB" -g $RG -n dev-ca-ricebridge-001 \
  --environment dev-cae-ricebridge-001 \
  --image devcrricebridge001.azurecr.io/ricebridge:<git-sha> \
  --registry-server devcrricebridge001.azurecr.io --registry-identity "$MI_ID" \
  --target-port 8080 --ingress external \
  --min-replicas 1 --max-replicas 1 --cpu 0.5 --memory 1.0Gi \
  --secrets "aoai-key=$AOAI_KEY" \
  --tags "${TAGS[@]}"
```

Biến môi trường của ứng dụng (đường dẫn dữ liệu, chế độ chạy, token người trình bày, mã khán giả) lấy theo [06 · Triển khai Container Apps](../design/redesign/06-cloud-deploy.md); bí mật đưa vào bằng `secretref:` trỏ tới secret đã tạo ở lệnh trên, không dán giá trị vào `--env-vars`. Không chép `AOAI_KEY` ra màn hình hay vào lịch sử lệnh.

## Kiểm tra sau khi tạo

```bash
az resource list --subscription "$SUB" -g $RG --query "[].{name:name,type:type,loc:location}" -o table
az cognitiveservices account deployment list --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 \
  --query "[].{name:name,model:properties.model.name,sku:sku.name,capacity:sku.capacity}" -o table
az acr show --subscription "$SUB" -g $RG -n devcrricebridge001 --query "{admin:adminUserEnabled,sku:sku.name}" -o table
```

Cần thấy: 5 tài nguyên cùng 2 deployment, `adminUserEnabled = false`, capacity 150 và 100. Có thể có thêm một resource group do nền tảng quản lý, tên dạng `ME_dev-cae-ricebridge-001_...`: đó là bình thường.

## Lấy endpoint và key cho `.env`

```bash
az cognitiveservices account show --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 --query properties.endpoint -o tsv
az cognitiveservices account keys list --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 --query key1 -o tsv
```

Dán vào `.env` (đã nằm trong `.gitignore`), **không** chép vào chat, ticket hay file được commit. Tên deployment dùng trong code là `fast` và `strong`.

## Bật và tắt Container App

Container App tính tiền theo thời gian chạy. Số replica tối thiểu có thể đổi bất cứ lúc nào:

```bash
az containerapp update --subscription "$SUB" -g $RG -n dev-ca-ricebridge-001 --min-replicas 0   # tắt về 0 khi không dùng: không tốn tiền chạy (ACR Basic vẫn tốn khoảng 5 USD/tháng)
az containerapp update --subscription "$SUB" -g $RG -n dev-ca-ricebridge-001 --min-replicas 1   # bật lại khi cần dev/test
```

Khi về 0, lần truy cập đầu tiên sẽ khởi động lại ứng dụng (mất vài giây) và **trạng thái trong RAM bị mất**. Đổi cấu hình replica có thể tạo revision mới và khởi động lại ứng dụng, nên không đổi giữa buổi trình diễn.

## Đổi model hoặc loại deployment sau khi tạo

Đổi capacity hoặc cách nâng cấp phiên bản làm tại chỗ được. Đổi **model** hoặc **loại** (`GlobalStandard` sang loại khác) phải xóa deployment rồi tạo lại cùng tên (`fast`/`strong`), mất vài phút, không mất dữ liệu:

```bash
az cognitiveservices account deployment delete --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 --deployment-name fast
```

rồi chạy lại lệnh tạo ở bước 7.

## Tắt hoặc xóa khi không dùng

**Tắt (không xóa)** là đủ khi chỉ tạm ngưng: đưa Container App về 0 replica (lệnh ở mục "Bật và tắt Container App"). Khi đó chỉ còn tốn **Container Registry Basic, khoảng 5 USD/tháng**; Azure OpenAI, Log Analytics (dưới mức miễn phí), identity và budget gần như không tốn. Có thể chạy lại bất cứ lúc nào, không phải tạo lại gì.

**Xóa hẳn** chỉ khi chắc chắn không dùng nữa (ví dụ không còn vòng thi nào). Lệnh dưới **không đảo ngược được**:

```bash
az group delete --subscription "$SUB" -n $RG --yes --no-wait
# đợi xóa xong, rồi purge account OpenAI đã bị xóa mềm (xóa mềm giữ 48 giờ và chặn tạo lại cùng tên)
az cognitiveservices account purge --subscription "$SUB" -g $RG -n dev-oai-ricebridge-001 -l japaneast
```

Purge cần quyền Contributor ở **phạm vi subscription**. Sau đó kiểm tra không còn resource group `ME_dev-cae-ricebridge-001_...` và budget đã được xóa hoặc hết hạn.
