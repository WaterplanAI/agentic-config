import assert from "node:assert/strict";
import { mkdtemp, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";

import {
  HookCompatGuardBlockedError,
  guardedRead,
  guardedWrite,
  listRegisteredHookCompatPackages,
} from "../index.js";
import { resetHookCompatRegistryForTests } from "../registry.js";
import { runHookCompatPreflight } from "../runtime.js";
import { UV_CACHE_DIR, UV_IS_AVAILABLE, cleanupPath } from "./helpers.js";

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

test(
  "runHookCompatPreflight blocks sensitive operations and allows safe direct calls with explicit registrations",
  { skip: !UV_IS_AVAILABLE, concurrency: false },
  async () => {
    resetHookCompatRegistryForTests();
    const workspace = await createRuntimeWorkspace("hook-compat-direct-preflight");

    try {
      await withTemporaryEnv({ HOME: workspace.homeDir, UV_CACHE_DIR }, async () => {
        const runtime = { name: "direct-preflight-runtime" };
        registerAcSafetyHookCompat(runtime);
        const registrations = listRegisteredHookCompatPackages(runtime);
        const allowedProjectDir = resolve(workspace.homeDir, "projects", "demo-app");
        await mkdir(allowedProjectDir, { recursive: true });

        const credentialReadResult = await runHookCompatPreflight({
          toolName: "read",
          input: { path: resolve(workspace.homeDir, ".ssh", "id_rsa") },
          cwd: workspace.projectDir,
          registrations,
        });
        assert.equal(credentialReadResult?.block, true);
        assert.match(credentialReadResult?.reason ?? "", /blocked|credential/i);

        const destructiveBashResult = await runHookCompatPreflight({
          toolName: "bash",
          input: { command: "rm -rf ~" },
          cwd: workspace.projectDir,
          registrations,
        });
        assert.equal(destructiveBashResult?.block, true);
        assert.match(destructiveBashResult?.reason ?? "", /blocked|rm -rf|destructive/i);

        const supplyChainResult = await runHookCompatPreflight({
          toolName: "bash",
          input: { command: "uv add evilpkg" },
          cwd: workspace.projectDir,
          registrations,
        });
        assert.equal(supplyChainResult?.block, true);
        assert.match(supplyChainResult?.reason ?? "", /confirm to proceed|unapproved package/i);

        const writeScopeResult = await runHookCompatPreflight({
          toolName: "write",
          input: { path: "/etc/hosts", content: "127.0.0.1 example.com\n" },
          cwd: workspace.projectDir,
          registrations,
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
          registrations,
        });
        assert.equal(notebookResult?.block, true);
        assert.match(notebookResult?.reason ?? "", /blocked|outside allowed|protected/i);

        const allowedReadResult = await runHookCompatPreflight({
          toolName: "read",
          input: { path: resolve(allowedProjectDir, "README.md") },
          cwd: allowedProjectDir,
          registrations,
        });
        assert.equal(allowedReadResult, undefined);

        const allowedWriteResult = await runHookCompatPreflight({
          toolName: "write",
          input: { path: resolve(allowedProjectDir, "notes.txt"), content: "safe\n" },
          cwd: allowedProjectDir,
          registrations,
        });
        assert.equal(allowedWriteResult, undefined);

        const allowedPlaywrightResult = await runHookCompatPreflight({
          toolName: "mcp__playwright__browser_snapshot",
          input: {},
          cwd: allowedProjectDir,
          registrations,
        });
        assert.equal(allowedPlaywrightResult, undefined);

        const guardedReadResult = await guardedRead({
          path: resolve(allowedProjectDir, "README.md"),
          cwd: allowedProjectDir,
          registrations,
          async execute({ input, cwd }) {
            return `${cwd}:${input.path}`;
          },
        });
        assert.match(guardedReadResult, /demo-app/);

        await assert.rejects(
          () =>
            guardedWrite({
              path: "/etc/hosts",
              content: "127.0.0.1 example.com\n",
              cwd: allowedProjectDir,
              registrations,
              async execute() {
                throw new Error("guardedWrite should not execute blocked writes");
              },
            }),
          (error) => {
            assert.equal(error instanceof HookCompatGuardBlockedError, true);
            assert.match(error.message, /blocked|outside allowed|protected/i);
            return true;
          },
        );
      });
    } finally {
      await cleanupPath(workspace.rootDir);
      resetHookCompatRegistryForTests();
    }
  },
);
