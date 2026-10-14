---
name: secrets-scan
description: Use before staging or pushing — scans the working tree and diff for secrets, tokens, connection strings, and PII. Recommends remediation.
---

# Secrets scan

## When to use

- Before `git add`/`git commit` for any change that touches config, infra, CI, or fixtures.
- Before opening a PR — re-run against `git diff main...HEAD`.
- Whenever the user pastes a snippet that may contain credentials.

## What to look for

| Category               | Patterns / signals                                                                 |
|------------------------|------------------------------------------------------------------------------------|
| Azure                  | `DefaultEndpointsProtocol=`, `AccountKey=`, `SharedAccessKey=`, `?sig=`, `https://*.blob.core.windows.net/.+sig=` |
| Azure AD               | client secrets `[A-Za-z0-9~._-]{34,}`, tenant + client id pairs in config         |
| AWS                    | `AKIA[0-9A-Z]{16}`, `aws_secret_access_key`                                        |
| GitHub                 | `ghp_[A-Za-z0-9]{36}`, `github_pat_`, `gho_`, `ghu_`, `ghs_`                       |
| Generic                | `Bearer [A-Za-z0-9._-]{20,}`, `password\s*=`, `api[-_ ]?key\s*=`, `secret\s*=`     |
| Private keys           | `-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----`                                     |
| DB URLs                | postgres / mssql / mongodb+srv URLs with embedded credentials (`user:password@host`) |
| PII                    | CMND/CCCD patterns, full names + DoB pairs in test fixtures                       |

## Procedure

1. Run `git diff --cached -U0` and read the diff. Do NOT just grep filenames.
2. For each match, classify:
   - **Real secret** → block the commit. Tell the user. Recommend `git restore --staged` + add to Key Vault.
   - **Example / placeholder** → require it to be obviously fake (`xxxx`, `REDACTED`, `00000000`). If it looks real, treat as real.
3. Check that `.env`, `*.tfvars`, `*.pfx`, `*.pem`, `*.key`, `kubeconfig`, `id_rsa*` aren't being added.
4. Cross-check against `.gitignore` — if any of the above paths aren't ignored, fix that first.
5. If tools are available, also run:
   ```bash
   gitleaks detect --staged --no-banner
   detect-secrets scan --baseline .secrets.baseline
   ```

## Output format

```
## Findings
- HIGH  path/to/file:LN — looks like an Azure storage AccountKey — block commit
- MED   path/to/file:LN — looks like a Bearer token in a comment — verify

## Recommended actions
- `git restore --staged path/to/file`
- Move value to Azure Key Vault; reference via `azurerm_key_vault_secret` data source
- If the secret was already pushed to a remote: rotate it first, then purge via BFG / `git filter-repo`

## Clean
- 0 findings → safe to proceed
```

## What to NEVER do

- Never echo a discovered secret back into your output beyond the minimum needed to identify it.
- Never auto-commit a "redaction" that just deletes the value — the secret may still be in git history. Tell the user to rotate.
