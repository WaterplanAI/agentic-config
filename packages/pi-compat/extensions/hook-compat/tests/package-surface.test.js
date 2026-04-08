import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

import hookCompatExtension, {
  HookCompatGuardBlockedError,
  guardedBash,
  guardedEdit,
  guardedGlob,
  guardedGrep,
  guardedNotebookEdit,
  guardedRead,
  guardedWrite,
  listRegisteredHookCompatPackages,
  registerHookCompatPackage,
  runHookCompatPreflight,
  runHookCompatToolCall,
} from "../index.js";
import { interpretHookDecision } from "../decision.js";
import { buildClaudeCompatEnv, resolveClaudeSessionId } from "../env.js";
import { resetHookCompatRegistryForTests } from "../registry.js";

function sampleRegistration(packageId = "package-surface") {
  return {
    packageId,
    pluginRoot: process.cwd(),
    hooks: [
      {
        matcher: "Bash",
        hooks: [
          {
            scriptPath: "scripts/hooks/example.py",
            failureMode: "fail-close",
          },
        ],
      },
    ],
  };
}

test("hook-compat exports the runtime extension, preflight helpers, guarded wrappers, and registration helpers", () => {
  resetHookCompatRegistryForTests();

  assert.equal(typeof hookCompatExtension, "function");
  assert.equal(typeof registerHookCompatPackage, "function");
  assert.equal(typeof listRegisteredHookCompatPackages, "function");
  assert.equal(typeof runHookCompatPreflight, "function");
  assert.equal(typeof runHookCompatToolCall, "function");
  assert.equal(typeof guardedRead, "function");
  assert.equal(typeof guardedGrep, "function");
  assert.equal(typeof guardedGlob, "function");
  assert.equal(typeof guardedBash, "function");
  assert.equal(typeof guardedWrite, "function");
  assert.equal(typeof guardedEdit, "function");
  assert.equal(typeof guardedNotebookEdit, "function");
  assert.equal(typeof HookCompatGuardBlockedError, "function");
});

test("registry state is shared across imports but isolated per runtime object", async () => {
  const registryUrl = new URL("../registry.js", import.meta.url);
  const firstModule = await import(`${registryUrl.href}?instance=first`);
  const secondModule = await import(`${registryUrl.href}?instance=second`);

  firstModule.resetHookCompatRegistryForTests();

  const runtimeA = { name: "runtime-a" };
  const runtimeB = { name: "runtime-b" };

  const firstResult = firstModule.registerHookCompatPackage(runtimeA, sampleRegistration("singleton-package"));
  const secondResult = secondModule.registerHookCompatPackage(runtimeA, {
    ...sampleRegistration("singleton-package"),
    pluginRoot: "/tmp/replaced-plugin-root",
  });
  const thirdResult = secondModule.registerHookCompatPackage(runtimeB, sampleRegistration("singleton-package"));

  assert.equal(firstResult.status, "registered");
  assert.equal(secondResult.status, "replaced");
  assert.equal(thirdResult.status, "registered");

  assert.equal(firstModule.listRegisteredHookCompatPackages(runtimeA).length, 1);
  assert.equal(secondModule.listRegisteredHookCompatPackages(runtimeA).length, 1);
  assert.equal(secondModule.listRegisteredHookCompatPackages(runtimeA)[0].pluginRoot, "/tmp/replaced-plugin-root");
  assert.equal(secondModule.listRegisteredHookCompatPackages(runtimeB).length, 1);
  assert.notEqual(
    secondModule.listRegisteredHookCompatPackages(runtimeA)[0].pluginRoot,
    secondModule.listRegisteredHookCompatPackages(runtimeB)[0].pluginRoot,
  );

  firstModule.resetHookCompatRegistryForTests();
});

test("extension registers one runtime handler set and clears only its own runtime state on shutdown", async () => {
  resetHookCompatRegistryForTests();

  const handlers = [];
  const pi = {
    on(eventName, handler) {
      handlers.push({ eventName, handler });
    },
  };
  const otherRuntime = { name: "other-runtime" };
  const toolCallEvent = {
    toolName: "bash",
    input: { command: "echo review-runtime" },
  };
  const ctx = {
    cwd: process.cwd(),
    hasUI: false,
    sessionManager: {
      getSessionId() {
        return "package-surface-session";
      },
    },
  };

  hookCompatExtension(pi);
  hookCompatExtension(pi);

  assert.equal(handlers.length, 3);
  assert.deepEqual(
    handlers.map((entry) => entry.eventName),
    ["tool_call", "user_bash", "session_shutdown"],
  );

  const toolCallHandler = handlers.find((entry) => entry.eventName === "tool_call")?.handler;
  const sessionShutdownHandler = handlers.find((entry) => entry.eventName === "session_shutdown")?.handler;
  const userBashHandler = handlers.find((entry) => entry.eventName === "user_bash")?.handler;

  assert.equal(typeof toolCallHandler, "function");
  assert.equal(typeof userBashHandler, "function");
  assert.equal(typeof sessionShutdownHandler, "function");

  registerHookCompatPackage(pi, sampleRegistration("shutdown-package"));
  registerHookCompatPackage(otherRuntime, sampleRegistration("other-runtime-package"));
  assert.equal(listRegisteredHookCompatPackages(pi).length, 1);
  assert.equal(listRegisteredHookCompatPackages(otherRuntime).length, 1);

  const beforeShutdownResult = await toolCallHandler(toolCallEvent, ctx);
  assert.equal(beforeShutdownResult?.block, true);
  assert.match(beforeShutdownResult?.reason ?? "", /example\.py|Hook adapter failure/i);

  await sessionShutdownHandler();
  assert.equal(listRegisteredHookCompatPackages(pi).length, 0);
  assert.equal(listRegisteredHookCompatPackages(otherRuntime).length, 1);

  const afterShutdownResult = await toolCallHandler(toolCallEvent, ctx);
  assert.equal(afterShutdownResult, undefined);
});


test("malformed hookSpecificOutput fails before user notification", async () => {
  const notifications = [];

  await assert.rejects(
    () =>
      interpretHookDecision({
        output: {
          systemMessage: "do-not-display",
          hookSpecificOutput: "bad-shape",
        },
        ctx: {
          hasUI: true,
          ui: {
            notify(message, level) {
              notifications.push({ message, level });
            },
          },
        },
        packageRegistration: { packageId: "pkg" },
        hookRegistration: { id: "hook" },
      }),
    /hookSpecificOutput must be an object/i,
  );

  assert.deepEqual(notifications, []);
});

test("resolveClaudeSessionId preserves safe ids and hashes unsafe session-file fallbacks", () => {
  const safeId = resolveClaudeSessionId({
    sessionManager: {
      getSessionId() {
        return "hook-compat-session";
      },
    },
  });
  assert.equal(safeId, "hook-compat-session");

  const hashedId = resolveClaudeSessionId({
    sessionManager: {
      getSessionFile() {
        return "/tmp/pi-compat/../../unsafe/session.json";
      },
    },
  });
  assert.match(hashedId, /^session-file-[a-f0-9]{24}$/);
  assert.equal(hashedId.includes("/"), false);
  assert.equal(
    hashedId,
    resolveClaudeSessionId({
      sessionManager: {
        getSessionFile() {
          return "/tmp/pi-compat/../../unsafe/session.json";
        },
      },
    }),
  );
});


test("buildClaudeCompatEnv normalizes unsafe session ids before exporting CLAUDE_SESSION_ID", () => {
  const env = buildClaudeCompatEnv({
    pluginRoot: "/tmp/plugin-root",
    projectDir: "/tmp/project-root",
    sessionId: "../../unsafe/session-id",
  });

  assert.match(env.CLAUDE_SESSION_ID, /^session-[a-f0-9]{24}$/);
  assert.equal(env.CLAUDE_SESSION_ID.includes("/"), false);
});


test("package.json wires hook-compat export surface", async () => {
  const packageJsonPath = fileURLToPath(new URL("../../../package.json", import.meta.url));
  const packageJson = JSON.parse(await readFile(packageJsonPath, "utf8"));

  assert.ok(packageJson.exports);
  assert.equal(
    packageJson.exports["./extensions/hook-compat"],
    "./extensions/hook-compat/index.js",
  );

  const packageRoot = fileURLToPath(new URL("../../..", import.meta.url));
  const importProbe = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      'const mod = await import("@agentic-config/pi-compat/extensions/hook-compat"); console.log(Object.keys(mod).sort().join(","));',
    ],
    {
      cwd: packageRoot,
      encoding: "utf8",
    },
  );

  assert.equal(importProbe.status, 0, importProbe.stderr);

  const exportedKeys = importProbe.stdout.trim().split(",").filter(Boolean);
  assert.deepEqual(exportedKeys, [
    "HookCompatGuardBlockedError",
    "default",
    "guardedBash",
    "guardedEdit",
    "guardedGlob",
    "guardedGrep",
    "guardedNotebookEdit",
    "guardedRead",
    "guardedWrite",
    "listRegisteredHookCompatPackages",
    "registerHookCompatPackage",
    "runHookCompatPreflight",
    "runHookCompatToolCall",
  ]);
});
