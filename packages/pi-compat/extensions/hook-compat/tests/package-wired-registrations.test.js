import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";

import { listRegisteredHookCompatPackages } from "../index.js";
import { resetHookCompatRegistryForTests } from "../registry.js";
import { runHookCompatPreflight, runHookCompatToolCall } from "../runtime.js";
import {
  REPO_ROOT,
  UV_CACHE_DIR,
  UV_IS_AVAILABLE,
  cleanupPath,
  createTestContext,
  createToolCallEvent,
  dateStampForToday,
} from "./helpers.js";

import registerAcAuditHookCompat from "../../../../pi-ac-audit/extensions/hook-compat.js";
import registerAcGitHookCompat from "../../../../pi-ac-git/extensions/hook-compat.js";
import registerAcSafetyHookCompat from "../../../../pi-ac-safety/extensions/hook-compat.js";
import registerAcToolsHookCompat from "../../../../pi-ac-tools/extensions/hook-compat.js";

function createRuntimeWorkspace(prefix) {
  return mkdtemp(join(tmpdir(), `${prefix}-`)).then(async (rootDir) => {
    const projectDir = resolve(rootDir, "project");
    const homeDir = resolve(rootDir, "home");

    await mkdir(projectDir, { recursive: true });
    await mkdir(homeDir, { recursive: true });

    return {
      rootDir,
      projectDir,
      homeDir,
    };
  });
}

async function withTemporaryEnv(overrides, fn) {
  const previousValues = new Map();

  try {
    for (const [key, value] of Object.entries(overrides)) {
      previousValues.set(key, process.env[key]);
      process.env[key] = value;
    }

    return await fn();
  } finally {
    for (const [key, previousValue] of previousValues.entries()) {
      if (previousValue === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = previousValue;
      }
    }
  }
}

function createRuntime(name) {
  return { name };
}

test("package extensions register packaged asset roots and expected hook tables", async () => {
  resetHookCompatRegistryForTests();

  const auditRuntime = createRuntime("audit-runtime");
  registerAcAuditHookCompat(auditRuntime);
  const [auditRegistration] = listRegisteredHookCompatPackages(auditRuntime);
  assert.equal(auditRegistration.packageId, "@agentic-config/pi-ac-audit");
  assert.equal(auditRegistration.pluginRoot, resolve(REPO_ROOT, "packages/pi-ac-audit/assets"));
  assert.deepEqual(auditRegistration.hooks.map((group) => group.matcher), ["*"]);
  assert.equal(auditRegistration.hooks[0].hooks[0].scriptPath, "scripts/hooks/tool-audit.py");

  const gitRuntime = createRuntime("git-runtime");
  registerAcGitHookCompat(gitRuntime);
  const [gitRegistration] = listRegisteredHookCompatPackages(gitRuntime);
  assert.equal(gitRegistration.packageId, "@agentic-config/pi-ac-git");
  assert.equal(gitRegistration.pluginRoot, resolve(REPO_ROOT, "packages/pi-ac-git/assets"));
  assert.deepEqual(gitRegistration.hooks.map((group) => group.matcher), ["Bash"]);
  assert.equal(gitRegistration.hooks[0].hooks[0].scriptPath, "scripts/hooks/git-commit-guard.py");

  const safetyRuntime = createRuntime("safety-runtime");
  registerAcSafetyHookCompat(safetyRuntime);
  const [safetyRegistration] = listRegisteredHookCompatPackages(safetyRuntime);
  assert.equal(safetyRegistration.packageId, "@agentic-config/pi-ac-safety");
  assert.equal(safetyRegistration.pluginRoot, resolve(REPO_ROOT, "packages/pi-ac-safety/assets"));
  assert.deepEqual(safetyRegistration.hooks.map((group) => group.matcher), [
    "Read|Grep|Glob",
    "Bash",
    "mcp__playwright__*|mcp__plugin_playwright_playwright__*",
    "Write|Edit|NotebookEdit",
  ]);
  assert.deepEqual(safetyRegistration.hooks[1].hooks.map((hook) => hook.scriptPath), [
    "scripts/hooks/destructive-bash-guardian.py",
    "scripts/hooks/supply-chain-guardian.py",
    "scripts/hooks/playwright-guardian.py",
  ]);
  assert.deepEqual(safetyRegistration.hooks[2].hooks.map((hook) => hook.scriptPath), [
    "scripts/hooks/playwright-guardian.py",
  ]);

  const toolsRuntime = createRuntime("tools-runtime");
  registerAcToolsHookCompat(toolsRuntime);
  const [toolsRegistration] = listRegisteredHookCompatPackages(toolsRuntime);
  assert.equal(toolsRegistration.packageId, "@agentic-config/pi-ac-tools");
  assert.equal(toolsRegistration.pluginRoot, resolve(REPO_ROOT, "packages/pi-ac-tools/assets"));
  assert.deepEqual(toolsRegistration.hooks.map((group) => group.matcher), ["Write|Edit|NotebookEdit|Bash", "Bash"]);
  assert.equal(toolsRegistration.hooks[0].hooks[0].failureMode, "fail-open");
  assert.equal(toolsRegistration.hooks[1].hooks[0].scriptPath, "scripts/hooks/gsuite-public-asset-guard.py");

  resetHookCompatRegistryForTests();
});

test(
  "package-wired audit and git registrations execute against packaged assets",
  { skip: !UV_IS_AVAILABLE, concurrency: false },
  async () => {
    resetHookCompatRegistryForTests();
    const workspace = await createRuntimeWorkspace("phase007-audit-git");

    try {
      await withTemporaryEnv({ HOME: workspace.homeDir, UV_CACHE_DIR }, async () => {
        const auditRuntime = createRuntime("audit-runtime");
        registerAcAuditHookCompat(auditRuntime);

        const auditContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: true,
        });

        const auditResult = await runHookCompatToolCall(
          createToolCallEvent("bash", { command: "echo packaged-audit" }),
          auditContext.ctx,
          { runtime: auditRuntime },
        );

        assert.equal(auditResult, undefined);
        assert.equal(auditContext.notifications.length > 0, true);
        assert.match(String(auditContext.notifications[0].message), /^Bash:/);

        const logFilePath = resolve(workspace.homeDir, ".claude", "audit-logs", `${dateStampForToday()}.jsonl`);
        const logContent = await readFile(logFilePath, "utf8");
        assert.match(logContent, /"tool"\s*:\s*"Bash"/);

        await writeFile(resolve(workspace.projectDir, "audit-log-target"), "x", "utf8");
        await writeFile(
          resolve(workspace.projectDir, "audit.yaml"),
          "log_dir: ./audit-log-target\ndisplay_tools:\n  - Bash\n",
          "utf8",
        );

        const failingAuditContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const failingAuditResult = await runHookCompatToolCall(
          createToolCallEvent("bash", { command: "echo packaged-audit-fail-close" }),
          failingAuditContext.ctx,
          { runtime: auditRuntime },
        );

        assert.equal(failingAuditResult?.block, true);
        assert.match(failingAuditResult?.reason ?? "", /Audit hook error \(fail-close\)/i);

        const gitRuntime = createRuntime("git-runtime");
        registerAcGitHookCompat(gitRuntime);

        const gitContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });

        const gitResult = await runHookCompatToolCall(
          createToolCallEvent("bash", { command: "git commit --no-verify -m 'test'" }),
          gitContext.ctx,
          { runtime: gitRuntime },
        );

        assert.equal(gitResult?.block, true);
        assert.match(gitResult?.reason ?? "", /--no-verify|Blocked/i);
      });
    } finally {
      await cleanupPath(workspace.rootDir);
      resetHookCompatRegistryForTests();
    }
  },
);

test(
  "package-wired safety registration preserves read, bash-chain, and write protections",
  { skip: !UV_IS_AVAILABLE, concurrency: false },
  async () => {
    resetHookCompatRegistryForTests();
    const workspace = await createRuntimeWorkspace("phase007-safety");

    try {
      await withTemporaryEnv({ HOME: workspace.homeDir, UV_CACHE_DIR }, async () => {
        const runtime = createRuntime("safety-runtime");
        registerAcSafetyHookCompat(runtime);

        const readContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const readResult = await runHookCompatToolCall(
          createToolCallEvent("read", { path: resolve(workspace.homeDir, ".ssh", "id_rsa") }),
          readContext.ctx,
          { runtime },
        );

        assert.equal(readResult?.block, true);
        assert.match(readResult?.reason ?? "", /blocked|credential/i);

        const bashContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const bashResult = await runHookCompatToolCall(
          createToolCallEvent("bash", { command: "uv add unapproved-package" }),
          bashContext.ctx,
          { runtime },
        );

        assert.equal(bashResult?.block, true);
        assert.match(bashResult?.reason ?? "", /confirm to proceed|unapproved package/i);

        const protectedWriteContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const protectedWriteResult = await runHookCompatToolCall(
          createToolCallEvent("bash", { command: "touch ~/.ssh/test" }),
          protectedWriteContext.ctx,
          { runtime },
        );

        assert.equal(protectedWriteResult?.block, true);
        assert.match(protectedWriteResult?.reason ?? "", /blocked|protected directory|ssh/i);

        const playwrightAllowContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const playwrightAllowResult = await runHookCompatToolCall(
          createToolCallEvent("bash", { command: "playwright-cli snapshot" }),
          playwrightAllowContext.ctx,
          { runtime },
        );

        assert.equal(playwrightAllowResult, undefined);

        const playwrightBlockedContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const playwrightBlockedResult = await runHookCompatToolCall(
          createToolCallEvent("bash", { command: "playwright-cli open https://evil.com/phishing" }),
          playwrightBlockedContext.ctx,
          { runtime },
        );

        assert.equal(playwrightBlockedResult?.block, true);
        assert.match(playwrightBlockedResult?.reason ?? "", /allowed domain list|confirm to proceed|playwright/i);

        const playwrightMcpBlockedContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const playwrightMcpBlockedResult = await runHookCompatToolCall(
          createToolCallEvent("mcp__playwright__browser_navigate", { url: "https://evil.com/phishing" }),
          playwrightMcpBlockedContext.ctx,
          { runtime },
        );

        assert.equal(playwrightMcpBlockedResult?.block, true);
        assert.match(playwrightMcpBlockedResult?.reason ?? "", /allowed domain list|confirm to proceed|playwright/i);

        const writeContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const writeResult = await runHookCompatToolCall(
          createToolCallEvent("write", { path: "/etc/hosts", content: "127.0.0.1 example.com\n" }),
          writeContext.ctx,
          { runtime },
        );

        assert.equal(writeResult?.block, true);
        assert.match(writeResult?.reason ?? "", /blocked|outside allowed|protected/i);

        const notebookContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const notebookResult = await runHookCompatToolCall(
          createToolCallEvent("NotebookEdit", {
            notebook_path: "/etc/unsafe.ipynb",
            cell_index: 0,
            new_source: "print('unsafe')\n",
          }),
          notebookContext.ctx,
          { runtime },
        );

        assert.equal(notebookResult?.block, true);
        assert.match(notebookResult?.reason ?? "", /blocked|outside allowed|protected/i);
      });
    } finally {
      await cleanupPath(workspace.rootDir);
      resetHookCompatRegistryForTests();
    }
  },
);

test(
  "package-wired safety registrations support direct preflight with live runtime state",
  { skip: !UV_IS_AVAILABLE, concurrency: false },
  async () => {
    resetHookCompatRegistryForTests();
    const workspace = await createRuntimeWorkspace("phase007-safety-direct-preflight");

    try {
      await withTemporaryEnv({ HOME: workspace.homeDir, UV_CACHE_DIR }, async () => {
        const runtime = createRuntime("safety-runtime-direct-preflight");
        registerAcSafetyHookCompat(runtime);

        const directContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });

        const credentialReadResult = await runHookCompatPreflight({
          toolName: "read",
          input: { path: resolve(workspace.homeDir, ".ssh", "id_rsa") },
          cwd: workspace.projectDir,
          ctx: directContext.ctx,
          runtime,
        });
        assert.equal(credentialReadResult?.block, true);
        assert.match(credentialReadResult?.reason ?? "", /blocked|credential/i);

        const destructiveBashResult = await runHookCompatPreflight({
          toolName: "bash",
          input: { command: "rm -rf ~" },
          cwd: workspace.projectDir,
          ctx: directContext.ctx,
          runtime,
        });
        assert.equal(destructiveBashResult?.block, true);
        assert.match(destructiveBashResult?.reason ?? "", /blocked|rm -rf|destructive/i);

        const supplyChainResult = await runHookCompatPreflight({
          toolName: "bash",
          input: { command: "uv add evilpkg" },
          cwd: workspace.projectDir,
          ctx: directContext.ctx,
          runtime,
        });
        assert.equal(supplyChainResult?.block, true);
        assert.match(supplyChainResult?.reason ?? "", /confirm to proceed|unapproved package/i);

        const writeScopeResult = await runHookCompatPreflight({
          toolName: "write",
          input: { path: "/etc/hosts", content: "127.0.0.1 example.com\n" },
          cwd: workspace.projectDir,
          ctx: directContext.ctx,
          runtime,
        });
        assert.equal(writeScopeResult?.block, true);
        assert.match(writeScopeResult?.reason ?? "", /blocked|outside allowed|protected/i);

        const notebookResult = await runHookCompatPreflight({
          toolName: "NotebookEdit",
          input: {
            notebook_path: "/etc/x.ipynb",
            cell_index: 0,
            new_source: "print('unsafe')\n",
          },
          cwd: workspace.projectDir,
          ctx: directContext.ctx,
          runtime,
        });
        assert.equal(notebookResult?.block, true);
        assert.match(notebookResult?.reason ?? "", /blocked|outside allowed|protected/i);
      });
    } finally {
      await cleanupPath(workspace.rootDir);
      resetHookCompatRegistryForTests();
    }
  },
);

test(
  "package-wired dry-run registration preserves deny, exception, and fail-open behavior",
  { skip: !UV_IS_AVAILABLE, concurrency: false },
  async () => {
    resetHookCompatRegistryForTests();
    const workspace = await createRuntimeWorkspace("phase007-dry-run");

    try {
      await withTemporaryEnv({ HOME: workspace.homeDir, UV_CACHE_DIR }, async () => {
        const runtime = createRuntime("tools-runtime");
        registerAcToolsHookCompat(runtime);

        const statusDir = resolve(workspace.projectDir, "outputs", "session", "shared");
        await mkdir(statusDir, { recursive: true });
        await writeFile(resolve(statusDir, "status.yml"), "dry_run: true\n", "utf8");

        const denyContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const denyResult = await runHookCompatToolCall(
          createToolCallEvent("write", { path: resolve(workspace.projectDir, "result.txt"), content: "test" }),
          denyContext.ctx,
          { runtime },
        );

        assert.equal(denyResult?.block, true);
        assert.match(denyResult?.reason ?? "", /Blocked by dry-run mode/i);

        const notebookContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const notebookResult = await runHookCompatToolCall(
          createToolCallEvent("NotebookEdit", {
            notebook_path: resolve(workspace.projectDir, "analysis.ipynb"),
            cell_index: 0,
            new_source: "print('blocked')\n",
          }),
          notebookContext.ctx,
          { runtime },
        );

        assert.equal(notebookResult?.block, true);
        assert.match(notebookResult?.reason ?? "", /Blocked by dry-run mode/i);

        const exceptionContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const exceptionResult = await runHookCompatToolCall(
          createToolCallEvent("write", { path: resolve(statusDir, "status.yml"), content: "dry_run: false\n" }),
          exceptionContext.ctx,
          { runtime },
        );

        assert.equal(exceptionResult, undefined);

        const registrations = listRegisteredHookCompatPackages(runtime);
        const brokenRegistrations = structuredClone(registrations);
        brokenRegistrations[0].hooks[0].hooks[0].scriptPath = "scripts/hooks/missing-dry-run-guard.py";

        const failOpenContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const failOpenResult = await runHookCompatToolCall(
          createToolCallEvent("write", { path: resolve(workspace.projectDir, "ignored.txt"), content: "test" }),
          failOpenContext.ctx,
          { registrations: brokenRegistrations },
        );

        assert.equal(failOpenResult, undefined);
      });
    } finally {
      await cleanupPath(workspace.rootDir);
      resetHookCompatRegistryForTests();
    }
  },
);

test(
  "package-wired gsuite guard blocks public sharing overrides while allowing private sharing",
  { skip: !UV_IS_AVAILABLE, concurrency: false },
  async () => {
    resetHookCompatRegistryForTests();
    const workspace = await createRuntimeWorkspace("phase007-gsuite-guard");

    try {
      await withTemporaryEnv({ HOME: workspace.homeDir, UV_CACHE_DIR }, async () => {
        const runtime = createRuntime("tools-runtime");
        registerAcToolsHookCompat(runtime);

        const blockedContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const blockedResult = await runHookCompatToolCall(
          createToolCallEvent("bash", {
            command:
              "uv run tools/drive.py share file-123 person@example.com --extra '{\"type\":\"anyone\",\"withLink\":true}'",
          }),
          blockedContext.ctx,
          { runtime },
        );

        assert.equal(blockedResult?.block, true);
        assert.match(blockedResult?.reason ?? "", /public GSuite assets|public sharing/i);

        const allowedContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });
        const allowedResult = await runHookCompatToolCall(
          createToolCallEvent("bash", {
            command: "uv run tools/drive.py share file-123 person@example.com --role writer",
          }),
          allowedContext.ctx,
          { runtime },
        );

        assert.equal(allowedResult, undefined);
      });
    } finally {
      await cleanupPath(workspace.rootDir);
      resetHookCompatRegistryForTests();
    }
  },
);
