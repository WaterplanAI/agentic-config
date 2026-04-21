import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";

import { runHookCompatToolCall } from "../runtime.js";
import {
  PLUGIN_ROOTS,
  UV_IS_AVAILABLE,
  buildHookEnv,
  cleanupPath,
  createTestContext,
  createToolCallEvent,
  dateStampForToday,
} from "./helpers.js";

function buildPackageRegistration(packageId, pluginRoot, hooks) {
  return {
    packageId,
    pluginRoot,
    askFallback: {
      nonInteractive: "deny",
    },
    hooks,
  };
}

function buildHookGroup(matcher, hooks) {
  return {
    matcher,
    hooks,
  };
}

function buildHook(scriptPath, homeDir, overrides = {}) {
  return {
    id: scriptPath,
    scriptPath,
    timeoutMs: 5000,
    failureMode: "fail-close",
    env: buildHookEnv(homeDir),
    ...overrides,
  };
}

async function createRuntimeWorkspace(prefix) {
  const rootDir = await mkdtemp(join(tmpdir(), `${prefix}-`));
  const projectDir = resolve(rootDir, "project");
  const homeDir = resolve(rootDir, "home");

  await mkdir(projectDir, { recursive: true });
  await mkdir(homeDir, { recursive: true });

  return {
    rootDir,
    projectDir,
    homeDir,
  };
}

test(
  "runtime integration: git-commit-guard deny path blocks immediately",
  { skip: !UV_IS_AVAILABLE },
  async () => {
    const workspace = await createRuntimeWorkspace("hook-compat-git-deny");

    try {
      const { ctx } = createTestContext({
        cwd: workspace.projectDir,
        hasUI: false,
      });

      const registrations = [
        buildPackageRegistration("ac-git", PLUGIN_ROOTS.acGit, [
          buildHookGroup("Bash", [
            buildHook("scripts/hooks/git-commit-guard.py", workspace.homeDir),
          ]),
        ]),
      ];

      const result = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "git commit --no-verify -m 'test'" }),
        ctx,
        { registrations },
      );

      assert.equal(result?.block, true);
      assert.match(result?.reason ?? "", /--no-verify|Blocked/i);
    } finally {
      await cleanupPath(workspace.rootDir);
    }
  },
);

test(
  "runtime integration: ask path handles UI confirmation and non-interactive fallback",
  { skip: !UV_IS_AVAILABLE },
  async () => {
    const workspace = await createRuntimeWorkspace("hook-compat-ask");

    try {
      const registrations = [
        buildPackageRegistration("ac-safety", PLUGIN_ROOTS.acSafety, [
          buildHookGroup("Bash", [
            buildHook("scripts/hooks/supply-chain-guardian.py", workspace.homeDir),
          ]),
        ]),
      ];

      const deniedByUser = createTestContext({
        cwd: workspace.projectDir,
        hasUI: true,
        confirmResult: false,
      });

      const deniedResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "uv add unapproved-package" }),
        deniedByUser.ctx,
        { registrations },
      );

      assert.equal(deniedResult?.block, true);
      assert.match(deniedResult?.reason ?? "", /Blocked by user|confirm to proceed/i);
      assert.equal(deniedByUser.confirmations.length, 1);

      const allowedByUser = createTestContext({
        cwd: workspace.projectDir,
        hasUI: true,
        confirmResult: true,
      });

      const allowedResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "uv add unapproved-package" }),
        allowedByUser.ctx,
        { registrations },
      );

      assert.equal(allowedResult, undefined);

      const nonInteractive = createTestContext({
        cwd: workspace.projectDir,
        hasUI: false,
      });

      const nonInteractiveResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "uv add unapproved-package" }),
        nonInteractive.ctx,
        { registrations },
      );

      assert.equal(nonInteractiveResult?.block, true);
      assert.match(nonInteractiveResult?.reason ?? "", /confirm to proceed|UI is unavailable/i);

      const nonInteractiveAllowRegistrations = [
        buildPackageRegistration("ac-safety-allow-fallback", PLUGIN_ROOTS.acSafety, [
          buildHookGroup("Bash", [
            buildHook("scripts/hooks/supply-chain-guardian.py", workspace.homeDir),
          ]),
        ]),
      ];
      nonInteractiveAllowRegistrations[0].askFallback.nonInteractive = "allow";

      const nonInteractiveAllowResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "uv add unapproved-package" }),
        nonInteractive.ctx,
        { registrations: nonInteractiveAllowRegistrations },
      );

      assert.equal(nonInteractiveAllowResult, undefined);
    } finally {
      await cleanupPath(workspace.rootDir);
    }
  },
);

test(
  "runtime integration: ordered destructive-bash then supply-chain chain preserves short-circuit behavior",
  { skip: !UV_IS_AVAILABLE },
  async () => {
    const workspace = await createRuntimeWorkspace("hook-compat-chain");

    try {
      const registrations = [
        buildPackageRegistration("ac-safety", PLUGIN_ROOTS.acSafety, [
          buildHookGroup("Bash", [
            buildHook("scripts/hooks/destructive-bash-guardian.py", workspace.homeDir),
            buildHook("scripts/hooks/supply-chain-guardian.py", workspace.homeDir),
          ]),
        ]),
      ];

      const context = createTestContext({
        cwd: workspace.projectDir,
        hasUI: false,
      });

      const destructiveResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "rm -rf /tmp/hook-compat-short-circuit" }),
        context.ctx,
        { registrations },
      );

      assert.equal(destructiveResult?.block, true);
      assert.match(destructiveResult?.reason ?? "", /destructive-bash-guardian|BLOCKED:/i);

      const supplyChainResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "uv add chain-package" }),
        context.ctx,
        { registrations },
      );

      assert.equal(supplyChainResult?.block, true);
      assert.match(supplyChainResult?.reason ?? "", /confirm to proceed|unapproved package/i);
    } finally {
      await cleanupPath(workspace.rootDir);
    }
  },
);

test(
  "runtime integration: audit hook allows systemMessage side effects and fail-closes on write errors",
  { skip: !UV_IS_AVAILABLE },
  async () => {
    const workspace = await createRuntimeWorkspace("hook-compat-audit");

    try {
      const registrations = [
        buildPackageRegistration("ac-audit", PLUGIN_ROOTS.acAudit, [
          buildHookGroup("*", [
            buildHook("scripts/hooks/tool-audit.py", workspace.homeDir),
          ]),
        ]),
      ];

      const successContext = createTestContext({
        cwd: workspace.projectDir,
        hasUI: true,
      });

      const successResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "echo audit-success" }),
        successContext.ctx,
        { registrations },
      );

      assert.equal(successResult, undefined);
      assert.equal(successContext.notifications.length > 0, true);
      assert.match(String(successContext.notifications[0].message), /^Bash:/);

      const logFilePath = resolve(
        workspace.homeDir,
        ".claude",
        "audit-logs",
        `${dateStampForToday()}.jsonl`,
      );
      const logContent = await readFile(logFilePath, "utf8");
      assert.match(logContent, /"tool"\s*:\s*"Bash"/);

      await writeFile(resolve(workspace.projectDir, "audit-log-target"), "x", "utf8");
      await writeFile(
        resolve(workspace.projectDir, "audit.yaml"),
        "log_dir: ./audit-log-target\ndisplay_tools:\n  - Bash\n",
        "utf8",
      );

      const failCloseContext = createTestContext({
        cwd: workspace.projectDir,
        hasUI: false,
      });

      const failCloseResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "echo audit-fail-close" }),
        failCloseContext.ctx,
        { registrations },
      );

      assert.equal(failCloseResult?.block, true);
      assert.match(failCloseResult?.reason ?? "", /Audit hook error \(fail-close\)/i);
    } finally {
      await cleanupPath(workspace.rootDir);
    }
  },
);

test(
  "runtime integration: dry-run hook adapter failures respect fail-open policy",
  { skip: !UV_IS_AVAILABLE },
  async () => {
    const workspace = await createRuntimeWorkspace("hook-compat-fail-open");

    try {
      const failOpenRegistrations = [
        buildPackageRegistration("ac-tools", PLUGIN_ROOTS.acTools, [
          buildHookGroup("Bash", [
            buildHook("scripts/hooks/missing-dry-run-guard.py", workspace.homeDir, {
              failureMode: "fail-open",
            }),
          ]),
        ]),
      ];

      const context = createTestContext({
        cwd: workspace.projectDir,
        hasUI: false,
      });

      const failOpenResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "echo fail-open" }),
        context.ctx,
        { registrations: failOpenRegistrations },
      );

      assert.equal(failOpenResult, undefined);

      const failCloseRegistrations = [
        buildPackageRegistration("ac-tools", PLUGIN_ROOTS.acTools, [
          buildHookGroup("Bash", [
            buildHook("scripts/hooks/missing-dry-run-guard.py", workspace.homeDir, {
              failureMode: "fail-close",
            }),
          ]),
        ]),
      ];

      const failCloseResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "echo fail-close" }),
        context.ctx,
        { registrations: failCloseRegistrations },
      );

      assert.equal(failCloseResult?.block, true);
      assert.match(failCloseResult?.reason ?? "", /Hook adapter failure|exited with code|missing-dry-run-guard/i);
    } finally {
      await cleanupPath(workspace.rootDir);
    }
  },
);

test(
  "runtime integration: malformed decision payloads respect fail-open vs fail-close policy",
  { skip: !UV_IS_AVAILABLE },
  async () => {
    const workspace = await createRuntimeWorkspace("hook-compat-malformed-decision");
    const pluginRoot = resolve(workspace.rootDir, "fixture-plugin");
    const scriptsDir = resolve(pluginRoot, "scripts", "hooks");
    const invalidDecisionScript = resolve(scriptsDir, "invalid-decision.py");

    try {
      await mkdir(scriptsDir, { recursive: true });
      await writeFile(
        invalidDecisionScript,
        `#!/usr/bin/env -S uv run --script\n# /// script\n# requires-python = \">=3.11\"\n# dependencies = []\n# ///\nimport json\nprint(json.dumps({\"hookSpecificOutput\": {\"hookEventName\": \"PreToolUse\", \"permissionDecision\": \"bogus\"}}))\n`,
        "utf8",
      );

      const context = createTestContext({
        cwd: workspace.projectDir,
        hasUI: false,
      });

      const failCloseRegistrations = [
        buildPackageRegistration("fixture-malformed-close", pluginRoot, [
          buildHookGroup("Bash", [
            buildHook("scripts/hooks/invalid-decision.py", workspace.homeDir, {
              failureMode: "fail-close",
            }),
          ]),
        ]),
      ];

      const failCloseResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "echo malformed-close" }),
        context.ctx,
        { registrations: failCloseRegistrations },
      );

      assert.equal(failCloseResult?.block, true);
      assert.match(failCloseResult?.reason ?? "", /Unsupported permissionDecision value|Hook adapter failure/i);

      const failOpenRegistrations = [
        buildPackageRegistration("fixture-malformed-open", pluginRoot, [
          buildHookGroup("Bash", [
            buildHook("scripts/hooks/invalid-decision.py", workspace.homeDir, {
              failureMode: "fail-open",
            }),
          ]),
        ]),
      ];

      const failOpenResult = await runHookCompatToolCall(
        createToolCallEvent("bash", { command: "echo malformed-open" }),
        context.ctx,
        { registrations: failOpenRegistrations },
      );

      assert.equal(failOpenResult, undefined);
    } finally {
      await cleanupPath(workspace.rootDir);
    }
  },
);
