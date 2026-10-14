---
name: azure-pipeline
description: Use when authoring or modifying CI/CD — Azure DevOps Pipelines or GitHub Actions. Enforces OIDC auth (no PATs), pinned actions, secrets via Key Vault, and staged approvals for prod.
---

# CI/CD — Azure DevOps Pipelines & GitHub Actions

## Rules (apply to both)

1. **OIDC, not long-lived secrets.** Auth to Azure via workload-identity federation. No service-principal passwords in pipeline variables.
2. **Secrets from Key Vault** at runtime (`AzureKeyVault@2` task / `azure/get-keyvault-secrets`). Never `secrets.MY_PASSWORD` for cloud creds.
3. **Pin third-party actions to a SHA**, not a floating tag: `uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1`.
4. **Least privilege**: pipeline service principals scoped per-env, prod ≠ dev SP.
5. **Branch protection**: `main` requires PR, status checks, 1 review, no direct push.
6. **Prod gates**: manual approval + change-window check before `terraform apply` or `kubectl apply` to prod.
7. **Caching by lockfile hash only.** Cache key includes `pnpm-lock.yaml` / `poetry.lock` / `uv.lock`. Never cache `node_modules` from a non-locked install.
8. **Artifacts are immutable.** Build once, promote the same image SHA across envs.
9. **No `set -x` with secrets exposed.** Use `::add-mask::` (GH) or `##vso[task.setsecret]` (ADO) for any value derived from a secret.

## Azure DevOps Pipelines — template

```yaml
# .azure-pipelines/ci.yml
trigger:
  branches: { include: [main] }
pr:
  branches: { include: [main] }

variables:
  - group: shared-non-secret
  - name: pythonVersion
    value: "3.12"

stages:
  - stage: Build
    jobs:
      - job: lint_test
        pool: { vmImage: ubuntu-latest }
        steps:
          - checkout: self
          - task: UsePythonVersion@0
            inputs: { versionSpec: $(pythonVersion) }
          - script: |
              pip install uv
              uv sync --frozen
            displayName: Install deps
          - script: uv run ruff check .
            displayName: Lint
          - script: uv run mypy app
            displayName: Type-check
          - script: uv run pytest -q --junitxml=junit.xml --cov=app
            displayName: Test
          - task: PublishTestResults@2
            condition: succeededOrFailed()
            inputs: { testResultsFiles: junit.xml }

  - stage: DeployDev
    dependsOn: Build
    condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
    jobs:
      - deployment: deploy
        environment: dev   # approvals + checks configured in ADO UI
        strategy:
          runOnce:
            deploy:
              steps:
                - task: AzureCLI@2
                  inputs:
                    azureSubscription: sc-dev-oidc
                    scriptType: bash
                    scriptLocation: inlineScript
                    inlineScript: |
                      az acr login -n $(ACR_NAME)
                      docker buildx build --push -t $(ACR_NAME).azurecr.io/app:$(Build.SourceVersion) .
```

## GitHub Actions — template

```yaml
# .github/workflows/ci.yml
name: ci
on:
  pull_request:
  push: { branches: [main] }

permissions:
  contents: read
  id-token: write   # OIDC to Azure

jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
      - uses: astral-sh/setup-uv@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86 # v3
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run mypy app
      - run: uv run pytest -q --cov=app

  deploy-dev:
    needs: lint-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: dev
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
      - uses: azure/login@a65d910e8af852a8061c627c456678983e180302 # v2.2.0
        with:
          client-id:       ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id:       ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - run: az acr login -n ${{ vars.ACR_NAME }}
      - run: |
          docker buildx build \
            --push \
            -t ${{ vars.ACR_NAME }}.azurecr.io/app:${{ github.sha }} .
```

## Dockerfile expectations referenced by CI

- Multi-stage, non-root user in final stage.
- No `ARG`/`ENV` containing secrets.
- Pin base image by digest for prod images.
- `hadolint` clean.
