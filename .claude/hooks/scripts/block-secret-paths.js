#!/usr/bin/env node
/**
 * PreToolUse guard for Read | Edit | Write | MultiEdit | NotebookEdit.
 *
 * Enforces CLAUDE.md security rule #1: "Never read or write secrets."
 * Denies any file operation whose target path looks like a secret/credential
 * file (.env, *.pem, *.key, *.pfx, id_rsa, kubeconfig, ~/.ssh, ~/.aws,
 * ~/.azure, anything under secrets/, *.tfvars, *.credentials.json).
 *
 * Written in Node (not bash) so it runs identically on Windows / macOS / Linux
 * — `node` always ships with Claude Code.
 *
 * Contract: read the PreToolUse event JSON on stdin, emit a deny decision on
 * stdout when the path is sensitive, otherwise exit 0 silently (= allow / fall
 * through to normal permission flow).
 */

function deny(reason) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: reason,
      },
    })
  );
  process.exit(0);
}

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
    // If nothing is piped, don't hang the tool call.
    setTimeout(() => resolve(data), 2000);
  });
}

// Rules return a human-readable reason string when the path is sensitive.
const RULES = [
  {
    test: (p, base) => base === ".env" || (base.startsWith(".env.") && base !== ".env.example"),
    why: "looks like an environment file that commonly holds secrets",
  },
  {
    test: (p) => /\.(pem|key|pfx|p12|crt|cer|keystore|jks)$/i.test(p),
    why: "looks like a private key / certificate file",
  },
  {
    test: (p, base) => /^id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$/i.test(base),
    why: "looks like an SSH private key",
  },
  {
    test: (p, base) => base === "kubeconfig" || base === ".credentials.json" || base === ".npmrc" || base === ".pypirc",
    why: "looks like a credentials / cluster-access file",
  },
  {
    test: (p) => /(^|\/)secrets\//i.test(p),
    why: "lives under a secrets/ directory",
  },
  {
    test: (p) => /(^|\/)\.(ssh|aws|azure|gnupg)\//i.test(p),
    why: "lives under a sensitive home directory (.ssh/.aws/.azure/.gnupg)",
  },
  {
    test: (p) => /\.tfvars$/i.test(p) && !/\.tfvars\.example$/i.test(p),
    why: "is a Terraform tfvars file that may contain secrets (use *.tfvars.example)",
  },
];

(async () => {
  let event;
  try {
    event = JSON.parse((await readStdin()) || "{}");
  } catch {
    process.exit(0); // Can't parse → don't block.
  }

  const input = event.tool_input || {};
  const raw = input.file_path || input.path || input.notebook_path || "";
  if (!raw) process.exit(0);

  const norm = String(raw).replace(/\\/g, "/");
  const base = norm.split("/").pop() || norm;

  for (const rule of RULES) {
    if (rule.test(norm, base)) {
      deny(
        `Blocked by di-claude-base hook (CLAUDE.md security rule #1: never read/write secrets). ` +
          `Path "${raw}" ${rule.why}. If you genuinely need this value, provide it via an env var at runtime ` +
          `or an Azure Key Vault reference — do not read it from disk.`
      );
    }
  }

  process.exit(0); // No match → allow.
})();
