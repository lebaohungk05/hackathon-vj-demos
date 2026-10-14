---
name: terraform-module
description: Use when authoring or modifying Terraform for Azure infrastructure. Enforces module layout, pinned providers, remote state, no-public-ingress defaults, and plan-before-apply.
---

# Terraform (Azure)

## Layout

```
infra/
  modules/<name>/        # reusable module — variables.tf, main.tf, outputs.tf, README.md
  envs/dev/              # env composition
  envs/staging/
  envs/prod/
  providers.tf           # pinned azurerm version, backend config
```

## Rules

1. **Pin providers** in every root: `azurerm ~> 4.0`, `random ~> 3.6`. Run `terraform init -upgrade` deliberately, never blindly.
2. **Remote state in Azure Storage** with locking enabled. Backend block goes in `providers.tf`, no secrets — auth via `ARM_USE_OIDC` from the pipeline.
3. **One module per logical unit** (e.g. `module-postgres`, `module-aks-cluster`). Modules have a `README.md` with inputs/outputs.
4. **Variables**: typed, with `description` and `validation` blocks. No untyped `any`.
5. **No `0.0.0.0/0` ingress.** NSGs must restrict to known CIDR or use Private Endpoints / Service Endpoints.
6. **Storage accounts**: `https_traffic_only_enabled = true`, `min_tls_version = "TLS1_2"`, `public_network_access_enabled = false` unless asked.
7. **Key Vaults**: RBAC mode (`enable_rbac_authorization = true`), no access policies, purge protection on for prod.
8. **No secrets in `.tf` or `.tfvars`.** Reference Key Vault via `azurerm_key_vault_secret` data sources.
9. **`tags`**: every resource gets the org tag set (`env`, `owner`, `cost_center`, `app`). Provide via a `local.common_tags` map.
10. **Destroy guards**: production state files require a manual approval gate in the pipeline. `terraform destroy` is never auto-approved.

## Workflow

```bash
terraform fmt -recursive
terraform validate
tflint
terraform plan -out=tfplan        # always plan first
# Review the plan with a human. Then:
terraform apply tfplan            # never -auto-approve in shared envs
```

## Module skeleton

```hcl
# modules/postgres/variables.tf
variable "name" {
  type        = string
  description = "Server name (3-63 chars, lowercase)."
  validation {
    condition     = can(regex("^[a-z0-9-]{3,63}$", var.name))
    error_message = "name must be lowercase alphanumeric + hyphen, 3-63 chars."
  }
}

variable "resource_group_name" { type = string }
variable "location"            { type = string }
variable "sku_name"            { type = string default = "GP_Standard_D2s_v3" }
variable "tags"                { type = map(string) default = {} }

# modules/postgres/main.tf
resource "azurerm_postgresql_flexible_server" "this" {
  name                          = var.name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku_name                      = var.sku_name
  public_network_access_enabled = false
  version                       = "16"
  tags                          = var.tags

  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = false
    tenant_id                     = data.azurerm_client_config.current.tenant_id
  }
}

# modules/postgres/outputs.tf
output "id"  { value = azurerm_postgresql_flexible_server.this.id }
output "fqdn" { value = azurerm_postgresql_flexible_server.this.fqdn }
```

## What NOT to do

- Don't generate `*.tfstate` reads/writes locally for shared envs — always use the remote backend.
- Don't `terraform import` without first writing the resource block.
- Don't widen a firewall rule "temporarily" — open a Bastion / JIT request instead.
