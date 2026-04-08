import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import registerStrictMuxRuntime, {
  getStrictRuntimeRegistryPath,
  resolveCurrentSessionKey,
} from "../index.js";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = path.resolve(TEST_DIR, "../../..");
const MUX_TOOLS_ROOT = path.join(PACKAGE_ROOT, "assets", "mux", "tools");

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `"'"'`)}'`;
}

function parseOutputValue(stdout, key) {
  const prefix = `${key}=`;
  for (const line of String(stdout).split(/\r?\n/)) {
    if (line.startsWith(prefix)) {
      return line.slice(prefix.length).trim();
    }
  }
  throw new Error(`Missing ${key} in output:\n${stdout}`);
}

async function createWorkspace(prefix) {
  const rootDir = await mkdtemp(path.join(tmpdir(), `${prefix}-`));
  await mkdir(path.join(rootDir, ".git"), { recursive: true });
  await mkdir(path.join(rootDir, ".specs", "specs"), { recursive: true });
  return rootDir;
}

async function cleanupWorkspace(rootDir) {
  await rm(rootDir, { recursive: true, force: true });
}

function createRuntime() {
  const handlers = [];
  registerStrictMuxRuntime({
    on(eventName, handler) {
      handlers.push({ eventName, handler });
    },
  });
  return {
    handlers,
    toolCallHandler: handlers.find((entry) => entry.eventName === "tool_call")?.handler,
  };
}

function createContext(workspace) {
  return {
    cwd: workspace,
    sessionManager: {
      getSessionFile() {
        return path.join(workspace, ".pi-session.json");
      },
      getSessionId() {
        return "strict-mux-runtime-test";
      },
    },
  };
}

function runShell(command, cwd) {
  return spawnSync("bash", ["-lc", command], {
    cwd,
    encoding: "utf8",
  });
}

async function bootstrapStrictSession(toolCallHandler, ctx, workspace, topicSlug = "strict-runtime") {
  const sessionCommand = [
    "uv run",
    shellQuote(path.join(MUX_TOOLS_ROOT, "session.py")),
    topicSlug,
    "--base",
    "tmp/mux-smoke",
    "--phase-id",
    "it005",
    "--stage-id",
    "phase-004",
    "--wave-id",
    "strict-runtime",
    "--strict-runtime",
  ].join(" ");

  const event = {
    toolName: "bash",
    input: {
      command: sessionCommand,
    },
  };
  const decision = await toolCallHandler(event, ctx);
  assert.equal(decision, undefined);
  assert.match(event.input.command, /--session-key/);

  const result = runShell(event.input.command, workspace);
  assert.equal(result.status, 0, result.stdout + result.stderr);

  return {
    sessionCommand: event.input.command,
    sessionDir: parseOutputValue(result.stdout, "SESSION_DIR"),
    registryPath: path.join(workspace, parseOutputValue(result.stdout, "STRICT_RUNTIME_REGISTRY")),
    activationFile: path.join(workspace, parseOutputValue(result.stdout, "STRICT_RUNTIME_FILE")),
    stdout: result.stdout,
  };
}

function runLedgerCommand(workspace, ...args) {
  const result = runShell(
    ["uv run", shellQuote(path.join(MUX_TOOLS_ROOT, "ledger.py")), ...args.map((value) => shellQuote(value))].join(" "),
    workspace,
  );
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result;
}

async function readLedger(workspace, sessionDir) {
  return JSON.parse(await readFile(path.join(workspace, sessionDir, ".mux-ledger.json"), "utf8"));
}

test("registers a workflow-owned tool_call guard", () => {
  const { toolCallHandler } = createRuntime();
  assert.equal(typeof toolCallHandler, "function");
});

test("non-strict sessions remain a no-op", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-noop");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);

    const result = await toolCallHandler(
      {
        toolName: "write",
        input: { path: "src/app.py", content: "print('noop')\n" },
      },
      ctx,
    );

    assert.equal(result, undefined);
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict bootstrap injects session key and writes activation registry", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-bootstrap");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "bootstrap");
    const sessionKey = resolveCurrentSessionKey(ctx);

    assert.ok(bootstrap.sessionCommand.includes("--session-key"));
    assert.equal(
      bootstrap.registryPath,
      getStrictRuntimeRegistryPath(workspace, sessionKey),
    );
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict mode blocks coordinator writes outside bounded orchestration paths", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-write-block");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    await bootstrapStrictSession(toolCallHandler, ctx, workspace, "write-block");

    const blocked = await toolCallHandler(
      {
        toolName: "write",
        input: { path: "src/app.py", content: "print('blocked')\n" },
      },
      ctx,
    );
    assert.equal(blocked?.block, true);
    assert.match(blocked?.reason ?? "", /outside the bounded orchestration paths/i);

    const allowed = await toolCallHandler(
      {
        toolName: "write",
        input: { path: ".specs/specs/demo.md", content: "# control plane\n" },
      },
      ctx,
    );
    assert.equal(allowed, undefined);
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict mode fails closed when the active ledger is missing", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-missing-ledger");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "missing-ledger");

    await rm(path.join(workspace, bootstrap.sessionDir, ".mux-ledger.json"), { force: true });

    const result = await toolCallHandler(
      {
        toolName: "write",
        input: { path: ".specs/specs/demo.md", content: "# blocked\n" },
      },
      ctx,
    );

    assert.equal(result?.block, true);
    assert.match(result?.reason ?? "", /Unable to load mux ledger|Ledger does not exist/i);
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict mode allows one declared single subagent dispatch and transitions to DISPATCH", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-valid-dispatch");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "valid-dispatch");

    const reportPath = "reports/strict-worker.md";
    const signalPath = `${bootstrap.sessionDir}/.signals/strict-worker.done`;
    const objective = "implement approved bounded change";
    const scope = "phase-004 approved files only";

    runLedgerCommand(workspace, "prerequisites", bootstrap.sessionDir, "--required", "phase-target", "--status", "ready");
    runLedgerCommand(workspace, "transition", bootstrap.sessionDir, "--to", "RESOLVE", "--reason", "phase target persisted");
    runLedgerCommand(workspace, "transition", bootstrap.sessionDir, "--to", "DECLARE", "--reason", "prerequisites evaluated");
    runLedgerCommand(
      workspace,
      "declare",
      bootstrap.sessionDir,
      "--worker-type",
      "worker",
      "--objective",
      objective,
      "--scope",
      scope,
      "--report-path",
      reportPath,
      "--signal-path",
      signalPath,
      "--expected-artifact",
      "report",
      "--expected-artifact",
      "signal",
      "--expected-artifact",
      "summary",
    );

    const task = [
      "Read and follow packages/pi-ac-workflow/assets/mux/protocol/subagent.md.",
      "",
      "Objective:",
      `- ${objective}`,
      "",
      "Constraints:",
      `- ${scope}`,
      "- No nested subagents",
      "",
      "Required report path:",
      `- ${reportPath}`,
      "",
      "Required signal path:",
      `- ${signalPath}`,
      "",
      "Before returning:",
      "- Write the report",
      "- Create the signal with packages/pi-ac-workflow/assets/mux/tools/signal.py",
      "- Return exactly 0 on success",
    ].join("\n");

    const decision = await toolCallHandler(
      {
        toolName: "subagent",
        input: { agent: "worker", task },
      },
      ctx,
    );

    assert.equal(decision, undefined);
    const ledger = await readLedger(workspace, bootstrap.sessionDir);
    assert.equal(ledger.control_state, "DISPATCH");
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict mode blocks vague subagent dispatches that do not match declared dispatch", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-invalid-dispatch");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "invalid-dispatch");

    runLedgerCommand(workspace, "prerequisites", bootstrap.sessionDir, "--required", "phase-target", "--status", "ready");
    runLedgerCommand(workspace, "transition", bootstrap.sessionDir, "--to", "RESOLVE", "--reason", "phase target persisted");
    runLedgerCommand(workspace, "transition", bootstrap.sessionDir, "--to", "DECLARE", "--reason", "prerequisites evaluated");
    runLedgerCommand(
      workspace,
      "declare",
      bootstrap.sessionDir,
      "--worker-type",
      "worker",
      "--objective",
      "implement approved bounded change",
      "--scope",
      "phase-004 approved files only",
      "--report-path",
      "reports/strict-worker.md",
      "--signal-path",
      `${bootstrap.sessionDir}/.signals/strict-worker.done`,
      "--expected-artifact",
      "report",
      "--expected-artifact",
      "signal",
      "--expected-artifact",
      "summary",
    );

    const decision = await toolCallHandler(
      {
        toolName: "subagent",
        input: {
          agent: "worker",
          task: [
            "Read and follow packages/pi-ac-workflow/assets/mux/protocol/subagent.md.",
            "",
            "Objective:",
            "- implement approved bounded change",
            "",
            "Constraints:",
            "- phase-004 approved files only",
            "",
            "Before returning:",
            "- Return exactly 0 on success",
          ].join("\n"),
        },
      },
      ctx,
    );

    assert.equal(decision?.block, true);
    assert.match(decision?.reason ?? "", /missing the declared signal path|missing the no-nested-subagents rule/i);
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict deactivate cleanup returns the session to non-strict behavior", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-deactivate");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    await bootstrapStrictSession(toolCallHandler, ctx, workspace, "deactivate");

    const deactivateEvent = {
      toolName: "bash",
      input: {
        command: `uv run ${shellQuote(path.join(MUX_TOOLS_ROOT, "deactivate.py"))}`,
      },
    };
    const decision = await toolCallHandler(deactivateEvent, ctx);
    assert.equal(decision, undefined);
    assert.match(deactivateEvent.input.command, /--session-key/);

    const result = runShell(deactivateEvent.input.command, workspace);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.equal(parseOutputValue(result.stdout, "STRICT_RUNTIME_DEACTIVATED"), "true");

    const afterCleanup = await toolCallHandler(
      {
        toolName: "write",
        input: { path: "src/app.py", content: "print('non-strict again')\n" },
      },
      ctx,
    );
    assert.equal(afterCleanup, undefined);
  } finally {
    await cleanupWorkspace(workspace);
  }
});
