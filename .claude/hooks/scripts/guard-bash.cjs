#!/usr/bin/env node
/**
 * PreToolUse guard for Bash.
 *
 * Enforces CLAUDE.md security rules:
 *   #2 Never commit secrets        -> scan `git commit` staged diff, DENY on a
 *                                     high-confidence secret.
 *   #3 No destructive ops w/o OK   -> force-push DENY; terraform destroy /
 *                                     az group delete / DROP|TRUNCATE -> ASK.
 *   #4 main/release are protected  -> `git push` while on a protected branch
 *                                     -> ASK.
 *
 * Node, not bash, for cross-platform parity with Claude Code's runtime.
 *
 * Contract: read PreToolUse JSON on stdin; emit a deny/ask decision when a
 * command trips a rule, otherwise exit 0 silently (allow / normal flow).
 */

const { execSync } = require("child_process");

function decide(decision, reason) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: decision, // "deny" | "ask"
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
    process.stdin.on("data", (c) => (data += c));
    process.stdin.on("end", () => resolve(data));
    setTimeout(() => resolve(data), 2000);
  });
}

// ----- secret detection (subset of the secrets-scan skill, high-confidence only) -----
const HIGH_CONFIDENCE = [
  { re: /-----BEGIN (RSA|EC|DSA|OPENSSH|PRIVATE) KEY-----/, cat: "private key" },
  { re: /AKIA[0-9A-Z]{16}/, cat: "AWS access key id" },
  { re: /\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b/, cat: "GitHub token" },
  { re: /\bgithub_pat_[A-Za-z0-9_]{40,}\b/, cat: "GitHub fine-grained PAT" },
  { re: /AccountKey=[A-Za-z0-9+/=]{40,}/, cat: "Azure storage AccountKey" },
  { re: /SharedAccessKey=[A-Za-z0-9+/=]{20,}/, cat: "Azure SharedAccessKey" },
  { re: /[?&]sig=[A-Za-z0-9%]{20,}/, cat: "Azure SAS signature" },
  { re: /(postgres|postgresql|mysql|mssql|mongodb(\+srv)?):\/\/[^:/\s]+:[^@\s]+@/, cat: "DB connection string with password" },
  { re: /xox[baprs]-[A-Za-z0-9-]{10,}/, cat: "Slack token" },
];
// Obvious placeholders that should NOT be treated as real.
const PLACEHOLDER = /(x{4,}|redacted|example|changeme|placeholder|dummy|<[^>]+>|0{6,}|your[-_]?\w+)/i;

function scanStagedDiffForSecrets(cwd) {
  let diff;
  try {
    diff = execSync("git diff --cached -U0", { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  } catch {
    return null; // not a git repo / git unavailable -> skip, don't block
  }
  const findings = [];
  let file = "?";
  for (const line of diff.split(/\r?\n/)) {
    const m = /^\+\+\+ b\/(.+)$/.exec(line);
    if (m) {
      file = m[1];
      continue;
    }
    if (!line.startsWith("+") || line.startsWith("+++")) continue;
    const added = line.slice(1);
    if (PLACEHOLDER.test(added)) continue;
    for (const { re, cat } of HIGH_CONFIDENCE) {
      if (re.test(added)) findings.push({ file, cat });
    }
  }
  return findings;
}

function currentBranch(cwd) {
  try {
    return execSync("git rev-parse --abbrev-ref HEAD", { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return null;
  }
}

const PROTECTED = /^(main|master|release($|\/)|releases\/)/i;

(async () => {
  let event;
  try {
    event = JSON.parse((await readStdin()) || "{}");
  } catch {
    process.exit(0);
  }

  const cmd = String((event.tool_input || {}).command || "");
  if (!cmd.trim()) process.exit(0);

  const cwd = event.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();

  // --- rule #3: force push is the most dangerous — hard deny ---
  if (/\bgit\s+push\b/.test(cmd) && /(--force\b|--force-with-lease|(^|\s)-f(\s|$))/.test(cmd)) {
    decide(
      "deny",
      "Blocked by di-claude-base hook (CLAUDE.md #3): force-pushing rewrites remote history. " +
        "The agent must not force-push. If you intend this, run it yourself in a terminal."
    );
  }

  // --- rule #3: irreversible infra/data destruction -> ask ---
  if (/\bterraform\s+destroy\b/.test(cmd)) {
    decide("ask", "di-claude-base hook (CLAUDE.md #3): `terraform destroy` is destructive — confirm before running.");
  }
  if (/\baz\s+group\s+delete\b/.test(cmd)) {
    decide("ask", "di-claude-base hook (CLAUDE.md #3): `az group delete` removes a whole resource group — confirm first.");
  }
  if (/\b(DROP|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA)\b/i.test(cmd) && /\b(psql|mysql|sqlcmd|mssql|mongo)\b/i.test(cmd)) {
    decide("ask", "di-claude-base hook (CLAUDE.md #3 / #6): DROP/TRUNCATE against a database — confirm this is not a non-local DB.");
  }

  // --- rule #2: never commit secrets ---
  if (/\bgit\s+commit\b/.test(cmd)) {
    const findings = scanStagedDiffForSecrets(cwd);
    if (findings && findings.length) {
      const uniq = [...new Map(findings.map((f) => [f.file + "|" + f.cat, f])).values()];
      const list = uniq.map((f) => `  - ${f.file}: ${f.cat}`).join("\n");
      decide(
        "deny",
        "Blocked by di-claude-base hook (CLAUDE.md #2): the staged diff appears to contain secret(s):\n" +
          list +
          "\nUnstage them (git restore --staged <file>), move the value to Azure Key Vault, then rotate if it was ever pushed."
      );
    }
  }

  // --- rule #4: don't push directly to protected branches ---
  if (/\bgit\s+push\b/.test(cmd) && !/--dry-run\b/.test(cmd)) {
    const branch = currentBranch(cwd);
    if (branch && PROTECTED.test(branch)) {
      decide(
        "ask",
        `di-claude-base hook (CLAUDE.md #4): you are on protected branch "${branch}". ` +
          "Prefer a feature branch + PR. Confirm if you really mean to push here."
      );
    }
  }

  process.exit(0); // no rule tripped -> allow
})();
