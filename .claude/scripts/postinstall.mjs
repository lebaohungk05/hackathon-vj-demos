#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PKG_ROOT = path.resolve(import.meta.dirname, '..');
const LOG_PREFIX = '[claude-base]';

// Env vars required by each MCP server (mirrors .mcp.json). playwright,
// filesystem and context7 need none.
const MCP_ENV = [
  { server: 'github (mcp)', vars: ['GITHUB_TOKEN'] },
  { server: 'azure-devops (mcp)', vars: ['AZURE_DEVOPS_ORG', 'AZURE_DEVOPS_PAT'] },
  { server: 'postgres (mcp)', vars: ['POSTGRES_READONLY_URL'] },
];

function log(...args) {
  console.log(LOG_PREFIX, ...args);
}

export function resolveClaudeHome(env = process.env) {
  return env.CLAUDE_CONFIG_DIR ?? path.join(os.homedir(), '.claude');
}

export function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

export function makeSymlink(target, linkPath, label) {
  let existing;
  try {
    existing = fs.lstatSync(linkPath);
  } catch {
    existing = null;
  }

  if (existing) {
    if (existing.isSymbolicLink()) {
      const current = fs.readlinkSync(linkPath);
      const resolvedCurrent = path.resolve(path.dirname(linkPath), current);
      if (resolvedCurrent === path.resolve(target)) {
        log(`${label}: already linked`);
        return;
      }
      log(`${label}: relinking (was -> ${current})`);
      fs.rmSync(linkPath);
    } else {
      log(
        `${label}: real directory at ${linkPath}, skipping to avoid data loss`
      );
      return;
    }
  }

  if (process.platform === 'win32') {
    try {
      fs.symlinkSync(target, linkPath, 'junction');
    } catch (err) {
      if (err.code === 'EPERM' || err.code === 'ENOTSUP') {
        log(
          `${label}: symlink not permitted, copying instead — updates will NOT auto-propagate`
        );
        fs.cpSync(target, linkPath, { recursive: true });
      } else {
        throw err;
      }
    }
  } else {
    fs.symlinkSync(target, linkPath);
  }

  log(`${label}: linked ${linkPath} -> ${target}`);
}

function unionArrays(a = [], b = []) {
  return [...new Set([...a, ...b])];
}

// Rewrite DI-managed hook command paths from project-relative
// (${CLAUDE_PROJECT_DIR}/.claude/hooks/scripts/) to the absolute installed
// location under <claudeHome>/hooks/shared/scripts/.
function rewriteHookPaths(settings, claudeHome) {
  if (!settings || typeof settings !== 'object' || !settings.hooks) {
    return settings;
  }
  const from = '${CLAUDE_PROJECT_DIR}/.claude/hooks/scripts/';
  const to = `${claudeHome}/hooks/shared/scripts/`;
  const json = JSON.stringify(settings.hooks).split(from).join(to);
  return { ...settings, hooks: JSON.parse(json) };
}

export function writeMcpJson() {
  const src = path.join(PKG_ROOT, '.mcp.json');
  const dest = path.join(os.homedir(), '.mcp.json');
  const incoming = JSON.parse(fs.readFileSync(src, 'utf8'));

  let result = incoming;
  if (fs.existsSync(dest)) {
    const current = JSON.parse(fs.readFileSync(dest, 'utf8'));
    // Merge: DI servers win on key collision; user-only servers are preserved.
    result = {
      ...current,
      mcpServers: { ...(current.mcpServers ?? {}), ...(incoming.mcpServers ?? {}) },
    };
    log('.mcp.json: merged into existing ~/.mcp.json');
  } else {
    log('.mcp.json: wrote ~/.mcp.json');
  }

  fs.writeFileSync(dest, JSON.stringify(result, null, 2) + '\n');
  return result;
}

export function writeSettings(claudeHome) {
  const src = path.join(PKG_ROOT, 'settings.json');
  const dest = path.join(claudeHome, 'settings.json');
  const incoming = rewriteHookPaths(
    JSON.parse(fs.readFileSync(src, 'utf8')),
    claudeHome
  );

  let result = incoming;
  if (fs.existsSync(dest)) {
    const current = JSON.parse(fs.readFileSync(dest, 'utf8'));
    // hooks are DI-managed: replace wholesale. Merge other keys conservatively.
    result = { ...current, ...incoming };
    if (current.permissions || incoming.permissions) {
      const cur = current.permissions ?? {};
      const inc = incoming.permissions ?? {};
      result.permissions = {
        ...cur,
        ...inc,
        allow: unionArrays(cur.allow, inc.allow),
        ask: unionArrays(cur.ask, inc.ask),
      };
    }
    if (current.enabledMcpjsonServers || incoming.enabledMcpjsonServers) {
      result.enabledMcpjsonServers = unionArrays(
        current.enabledMcpjsonServers,
        incoming.enabledMcpjsonServers
      );
    }
    if (incoming.hooks) result.hooks = incoming.hooks;
    log(`settings.json: merged into existing ${dest}`);
  } else {
    log(`settings.json: wrote ${dest}`);
  }

  fs.writeFileSync(dest, JSON.stringify(result, null, 2) + '\n');
  return result;
}

function pad(str, width) {
  return str + ' '.repeat(Math.max(0, width - str.length));
}

export function printEnvReport(env = process.env, out = console.log) {
  const width = Math.max(
    ...MCP_ENV.flatMap((g) => g.vars.map((v) => v.length)),
    18
  );
  const line = '─'.repeat(49);
  out('');
  out('@di/claude-base — required environment variables');
  out(line);
  for (const group of MCP_ENV) {
    out(`${group.server}:`);
    for (const v of group.vars) {
      const status = env[v] ? 'set' : 'missing';
      out(`  ${pad(v, width)}  ${status}`);
    }
  }
  out('playwright, filesystem, context7: no env vars required');
  out(line);
  out('Add missing vars to your shell profile or .env file.');
  out('');
}

export function runPostinstall(env = process.env) {
  const claudeHome = resolveClaudeHome(env);

  for (const dir of [
    path.join(claudeHome, 'agents'),
    path.join(claudeHome, 'agents', 'local'),
    path.join(claudeHome, 'skills'),
    path.join(claudeHome, 'skills', 'local'),
    path.join(claudeHome, 'hooks'),
    path.join(claudeHome, 'references'),
    path.join(claudeHome, 'assets'),
  ]) {
    ensureDir(dir);
  }

  makeSymlink(
    path.join(PKG_ROOT, 'agents'),
    path.join(claudeHome, 'agents', 'shared'),
    'agents/shared'
  );
  makeSymlink(
    path.join(PKG_ROOT, 'skills'),
    path.join(claudeHome, 'skills', 'shared'),
    'skills/shared'
  );
  makeSymlink(
    path.join(PKG_ROOT, 'hooks'),
    path.join(claudeHome, 'hooks', 'shared'),
    'hooks/shared'
  );
  makeSymlink(
    path.join(PKG_ROOT, 'references'),
    path.join(claudeHome, 'references', 'shared'),
    'references/shared'
  );
  makeSymlink(
    path.join(PKG_ROOT, 'assets'),
    path.join(claudeHome, 'assets', 'shared'),
    'assets/shared'
  );

  writeMcpJson();
  writeSettings(claudeHome);
  printEnvReport(env);
}

function main() {
  try {
    if (process.env.CLAUDE_BASE_SKIP_POSTINSTALL) {
      log('CLAUDE_BASE_SKIP_POSTINSTALL set — skipping postinstall.');
      process.exit(0);
    }
    runPostinstall();
  } catch (err) {
    console.warn(LOG_PREFIX, 'postinstall warning:', err.message);
    console.warn(LOG_PREFIX, 'run `npx claude-base-link` to retry linking.');
    process.exit(0);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main();
}
