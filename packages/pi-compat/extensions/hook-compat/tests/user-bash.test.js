import assert from "node:assert/strict";
import { mkdtemp, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";

import hookCompatExtension from "../index.js";
import { resetHookCompatRegistryForTests } from "../registry.js";
import { UV_CACHE_DIR, UV_IS_AVAILABLE, cleanupPath, createTestContext } from "./helpers.js";

import registerAcSafetyHookCompat from "../../../../pi-ac-safety/extensions/hook-compat.js";

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

function createHookCompatRuntime() {
  const handlers = new Map();
  const runtime = {
    on(eventName, handler) {
      const existingHandlers = handlers.get(eventName) ?? [];
      existingHandlers.push(handler);
      handlers.set(eventName, existingHandlers);
    },
  };

  return {
    runtime,
    handlers,
  };
}

test(
  "user_bash blocks guarded commands before execution and allows safe commands through",
  { skip: !UV_IS_AVAILABLE, concurrency: false },
  async () => {
    resetHookCompatRegistryForTests();
    const workspace = await createRuntimeWorkspace("hook-compat-user-bash");

    try {
      await withTemporaryEnv({ HOME: workspace.homeDir, UV_CACHE_DIR }, async () => {
        const { runtime, handlers } = createHookCompatRuntime();
        hookCompatExtension(runtime);
        registerAcSafetyHookCompat(runtime);

        const [userBashHandler] = handlers.get("user_bash") ?? [];
        assert.equal(typeof userBashHandler, "function");

        const blockedContext = createTestContext({
          cwd: workspace.projectDir,
          hasUI: false,
        });

        const credentialReadResult = await userBashHandler(
          {
            type: "user_bash",
            command: "cat ~/.ssh/id_rsa",
            excludeFromContext: false,
            cwd: workspace.projectDir,
          },
          blockedContext.ctx,
        );
        assert.equal(typeof credentialReadResult?.result?.output, "string");
        assert.equal(credentialReadResult?.result?.exitCode, 126);
        assert.match(credentialReadResult?.result?.output ?? "", /blocked|credential|ssh/i);

        const playwrightBlockedResult = await userBashHandler(
          {
            type: "user_bash",
            command: "playwright-cli open https://evil.com/phishing",
            excludeFromContext: true,
            cwd: workspace.projectDir,
          },
          blockedContext.ctx,
        );
        assert.equal(playwrightBlockedResult?.result?.exitCode, 126);
        assert.match(playwrightBlockedResult?.result?.output ?? "", /allowed domain list|confirm to proceed|playwright/i);

        const safeCommandResult = await userBashHandler(
          {
            type: "user_bash",
            command: "echo safe-command",
            excludeFromContext: false,
            cwd: workspace.projectDir,
          },
          blockedContext.ctx,
        );
        assert.equal(safeCommandResult, undefined);
      });
    } finally {
      await cleanupPath(workspace.rootDir);
      resetHookCompatRegistryForTests();
    }
  },
);
