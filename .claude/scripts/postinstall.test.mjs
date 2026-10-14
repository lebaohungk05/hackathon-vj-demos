import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const SCRIPT = fileURLToPath(new URL('./postinstall.mjs', import.meta.url));
const PKG_ROOT = path.resolve(path.dirname(SCRIPT), '..');

function freshHome() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'claude-base-test-'));
}

function runInstall(claudeHome, extraEnv = {}) {
  const res = spawnSync(process.execPath, [SCRIPT], {
    env: {
      ...process.env,
      CLAUDE_CONFIG_DIR: claudeHome,
      CLAUDE_BASE_SKIP_POSTINSTALL: '',
      ...extraEnv,
    },
    encoding: 'utf8',
  });
  return res;
}

test('fresh install creates shared symlinks and real local dirs', () => {
  const home = freshHome();
  const res = runInstall(home);
  assert.equal(res.status, 0, res.stderr);

  for (const group of ['agents', 'skills']) {
    const shared = path.join(home, group, 'shared');
    const local = path.join(home, group, 'local');
    assert.ok(fs.lstatSync(shared).isSymbolicLink(), `${group}/shared is symlink`);
    assert.equal(
      fs.realpathSync(shared),
      fs.realpathSync(path.join(PKG_ROOT, group)),
      `${group}/shared points at package dir`
    );
    assert.ok(
      fs.statSync(local).isDirectory() && !fs.lstatSync(local).isSymbolicLink(),
      `${group}/local is a real dir`
    );
  }

  assert.ok(
    fs.lstatSync(path.join(home, 'hooks', 'shared')).isSymbolicLink(),
    'hooks/shared is symlink'
  );
  assert.ok(
    fs.lstatSync(path.join(home, 'references', 'shared')).isSymbolicLink(),
    'references/shared is symlink'
  );
});

test('idempotent: running twice leaves symlinks unchanged', () => {
  const home = freshHome();
  assert.equal(runInstall(home).status, 0);
  const before = fs.readlinkSync(path.join(home, 'agents', 'shared'));

  const second = runInstall(home);
  assert.equal(second.status, 0, second.stderr);
  assert.match(second.stdout, /agents\/shared: already linked/);

  const after = fs.readlinkSync(path.join(home, 'agents', 'shared'));
  assert.equal(before, after);
});

test('clobber-safety: real dir at shared path is preserved', () => {
  const home = freshHome();
  const shared = path.join(home, 'agents', 'shared');
  fs.mkdirSync(shared, { recursive: true });
  const sentinel = path.join(shared, 'keep.txt');
  fs.writeFileSync(sentinel, 'do not delete');

  const res = runInstall(home);
  assert.equal(res.status, 0, res.stderr);
  assert.match(res.stdout, /real directory at .*agents.shared, skipping/);
  assert.ok(fs.existsSync(sentinel), 'sentinel file survived');
  assert.equal(fs.readFileSync(sentinel, 'utf8'), 'do not delete');
  assert.ok(!fs.lstatSync(shared).isSymbolicLink(), 'still a real dir');
});

test('settings.json is written with hook paths under claudeHome, not project dir', () => {
  const home = freshHome();
  const res = runInstall(home);
  assert.equal(res.status, 0, res.stderr);

  const dest = path.join(home, 'settings.json');
  assert.ok(fs.existsSync(dest), 'settings.json written');
  const parsed = JSON.parse(fs.readFileSync(dest, 'utf8'));
  const commands = parsed.hooks.PreToolUse.flatMap((m) =>
    m.hooks.map((h) => h.command)
  );
  for (const cmd of commands) {
    assert.ok(
      !cmd.includes('${CLAUDE_PROJECT_DIR}'),
      `no project-relative hook path in: ${cmd}`
    );
    assert.ok(
      cmd.includes(`${home}/hooks/shared/scripts/`),
      `hook path references temp claudeHome in: ${cmd}`
    );
  }
});

test('settings merge preserves existing user permissions', () => {
  const home = freshHome();
  fs.mkdirSync(home, { recursive: true });
  fs.writeFileSync(
    path.join(home, 'settings.json'),
    JSON.stringify({
      permissions: { allow: ['Bash(my-custom-cmd:*)'] },
      myCustomKey: true,
    })
  );

  const res = runInstall(home);
  assert.equal(res.status, 0, res.stderr);
  const parsed = JSON.parse(fs.readFileSync(path.join(home, 'settings.json'), 'utf8'));
  assert.ok(parsed.permissions.allow.includes('Bash(my-custom-cmd:*)'));
  assert.ok(parsed.permissions.allow.includes('Bash(ruff:*)'));
  assert.equal(parsed.myCustomKey, true);
});

test('settings merge with partial existing settings preserves user key and adds DI permissions', () => {
  const home = freshHome();
  fs.mkdirSync(home, { recursive: true });
  fs.writeFileSync(
    path.join(home, 'settings.json'),
    JSON.stringify({ someKey: true })
  );

  const res = runInstall(home);
  assert.equal(res.status, 0, res.stderr);

  const parsed = JSON.parse(fs.readFileSync(path.join(home, 'settings.json'), 'utf8'));
  // user's arbitrary key survives the merge
  assert.equal(parsed.someKey, true);
  // DI permissions get introduced even though the user had none
  assert.ok(parsed.permissions, 'permissions block present');
  assert.ok(parsed.permissions.allow.includes('Bash(ruff:*)'));
  assert.ok(parsed.permissions.ask.includes('Bash(git push:*)'));
});

test('settings merge: DI defaultMode overwrites user defaultMode (DI preference wins)', () => {
  const home = freshHome();
  fs.mkdirSync(home, { recursive: true });
  fs.writeFileSync(
    path.join(home, 'settings.json'),
    JSON.stringify({ permissions: { defaultMode: 'plan' } })
  );

  const res = runInstall(home);
  assert.equal(res.status, 0, res.stderr);

  const parsed = JSON.parse(fs.readFileSync(path.join(home, 'settings.json'), 'utf8'));
  // The merge is {...cur, ...inc}, so DI's defaultMode (acceptEdits) overrides
  // the user's 'plan'. This is the documented/accepted behavior: DI wins.
  assert.equal(parsed.permissions.defaultMode, 'acceptEdits');
});

test('assets/shared symlink is created', () => {
  const home = freshHome();
  const res = runInstall(home);
  assert.equal(res.status, 0, res.stderr);

  const shared = path.join(home, 'assets', 'shared');
  assert.ok(fs.lstatSync(shared).isSymbolicLink(), 'assets/shared is symlink');
  assert.equal(
    fs.realpathSync(shared),
    fs.realpathSync(path.join(PKG_ROOT, 'assets')),
    'assets/shared points at package assets dir'
  );
});

test('.mcp.json is copied to home dir', () => {
  const tmpHome = freshHome();
  const mcpDest = path.join(tmpHome, '.mcp.json');
  const res = spawnSync(process.execPath, [SCRIPT], {
    env: {
      ...process.env,
      CLAUDE_CONFIG_DIR: freshHome(),
      HOME: tmpHome,
      USERPROFILE: tmpHome,
      CLAUDE_BASE_SKIP_POSTINSTALL: '',
    },
    encoding: 'utf8',
  });
  assert.equal(res.status, 0, res.stderr);
  assert.ok(fs.existsSync(mcpDest), '~/.mcp.json written');
  const parsed = JSON.parse(fs.readFileSync(mcpDest, 'utf8'));
  assert.ok(parsed.mcpServers && typeof parsed.mcpServers === 'object', 'has mcpServers');
});

test('.mcp.json merge preserves user-only servers', () => {
  const tmpHome = freshHome();
  const mcpDest = path.join(tmpHome, '.mcp.json');
  fs.writeFileSync(mcpDest, JSON.stringify({ mcpServers: { 'my-server': { command: 'my-cmd' } } }));

  spawnSync(process.execPath, [SCRIPT], {
    env: {
      ...process.env,
      CLAUDE_CONFIG_DIR: freshHome(),
      HOME: tmpHome,
      USERPROFILE: tmpHome,
      CLAUDE_BASE_SKIP_POSTINSTALL: '',
    },
    encoding: 'utf8',
  });

  const parsed = JSON.parse(fs.readFileSync(mcpDest, 'utf8'));
  assert.ok(parsed.mcpServers['my-server'], 'user server preserved');
  assert.ok(parsed.mcpServers['github'], 'DI github server present');
});

test('CLAUDE_BASE_SKIP_POSTINSTALL skips all work', () => {
  const home = freshHome();
  const res = runInstall(home, { CLAUDE_BASE_SKIP_POSTINSTALL: '1' });
  assert.equal(res.status, 0, res.stderr);
  assert.match(res.stdout, /skipping postinstall/);
  assert.ok(!fs.existsSync(path.join(home, 'agents', 'shared')));
});
