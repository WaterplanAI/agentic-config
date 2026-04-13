import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
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
    "tmp/mux",
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

async function bootstrapObservabilityOnlySession(toolCallHandler, ctx, workspace, topicSlug = "observability-only") {
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
    "observability",
  ].join(" ");

  const event = {
    toolName: "bash",
    input: {
      command: sessionCommand,
    },
  };
  const decision = await toolCallHandler(event, ctx);
  assert.equal(decision, undefined);

  const result = runShell(event.input.command, workspace);
  assert.equal(result.status, 0, result.stdout + result.stderr);

  return {
    sessionDir: parseOutputValue(result.stdout, "SESSION_DIR"),
    markerPath: path.join(workspace, parseOutputValue(result.stdout, "MUX_ACTIVE")),
    strictRuntime: parseOutputValue(result.stdout, "STRICT_RUNTIME"),
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

async function writeWorkerReport(workspace, reportPath) {
  const absolutePath = path.join(workspace, reportPath);
  await mkdir(path.dirname(absolutePath), { recursive: true });
  await writeFile(
    absolutePath,
    [
      "# Worker Report",
      "",
      "## Table of Contents",
      "- Item",
      "",
      "## Executive Summary",
      "- **Status**: pass",
      `- **Files**: ${reportPath}`,
      "",
      "### Next Steps",
      "- **Recommended action**: continue",
      "- **Dependencies**: none",
      "- **Routing hint**: writer",
      "",
    ].join("\n"),
    "utf8",
  );
}

function emitSuccessSignal(workspace, signalPath, reportPath) {
  const result = runShell(
    [
      "uv run",
      shellQuote(path.join(MUX_TOOLS_ROOT, "signal.py")),
      shellQuote(signalPath),
      "--path",
      shellQuote(reportPath),
      "--status",
      "success",
    ].join(" "),
    workspace,
  );
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result;
}

function emitSummaryEvidence(workspace, reportPath, summaryEvidencePath) {
  const result = runShell(
    [
      "uv run",
      shellQuote(path.join(MUX_TOOLS_ROOT, "extract-summary.py")),
      shellQuote(reportPath),
      "--evidence",
      "--evidence-path",
      shellQuote(summaryEvidencePath),
    ].join(" "),
    workspace,
  );
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result;
}

function runVerifyGate(workspace, sessionDir, summaryEvidencePath) {
  return runShell(
    [
      "uv run",
      shellQuote(path.join(MUX_TOOLS_ROOT, "verify.py")),
      shellQuote(sessionDir),
      "--action",
      "gate",
      "--summary-evidence",
      shellQuote(summaryEvidencePath),
    ].join(" "),
    workspace,
  );
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

test("observability marker alone does not activate strict mode", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-observability-only");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const markerOnly = await bootstrapObservabilityOnlySession(toolCallHandler, ctx, workspace);

    assert.equal(markerOnly.strictRuntime, "false");
    const markerContents = await readFile(markerOnly.markerPath, "utf8");
    assert.match(markerContents, /tmp\/mux-smoke\//);

    const result = await toolCallHandler(
      {
        toolName: "write",
        input: { path: "src/app.py", content: "print('still non-strict')\n" },
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


test("strict bootstrap overrides a foreign session key with the current session key", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-bootstrap-override");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const sessionKey = resolveCurrentSessionKey(ctx);

    const event = {
      toolName: "bash",
      input: {
        command: [
          "uv run",
          shellQuote(path.join(MUX_TOOLS_ROOT, "session.py")),
          "override-key",
          "--base",
          "tmp/mux",
          "--phase-id",
          "it005",
          "--stage-id",
          "phase-004",
          "--wave-id",
          "strict-runtime",
          "--strict-runtime",
          "--session-key",
          "foreign-session-key",
        ].join(" "),
      },
    };

    const decision = await toolCallHandler(event, ctx);
    assert.equal(decision, undefined);
    assert.ok(event.input.command.includes(sessionKey));
    assert.doesNotMatch(event.input.command, /foreign-session-key/);

    const result = runShell(event.input.command, workspace);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.equal(
      path.join(workspace, parseOutputValue(result.stdout, "STRICT_RUNTIME_REGISTRY")),
      getStrictRuntimeRegistryPath(workspace, sessionKey),
    );
  } finally {
    await cleanupWorkspace(workspace);
  }
});


test("strict bootstrap cannot re-run after strict activation exists for the current session", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-bootstrap-reentry");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    await bootstrapStrictSession(toolCallHandler, ctx, workspace, "bootstrap-first");

    const reentryDecision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: [
            "uv run",
            shellQuote(path.join(MUX_TOOLS_ROOT, "session.py")),
            "bootstrap-reentry",
            "--base",
            "tmp/mux",
            "--phase-id",
            "it005",
            "--stage-id",
            "phase-004",
            "--wave-id",
            "strict-runtime",
            "--strict-runtime",
          ].join(" "),
        },
      },
      ctx,
    );

    assert.equal(reentryDecision?.block, true);
    assert.match(reentryDecision?.reason ?? "", /strict bootstrap is only allowed before strict activation is established/i);
  } finally {
    await cleanupWorkspace(workspace);
  }
});


test("strict bootstrap rejects bases outside the project-local tmp/mux tree", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-bootstrap-base");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);

    const directEscapeDecision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: [
            "uv run",
            shellQuote(path.join(MUX_TOOLS_ROOT, "session.py")),
            "invalid-base",
            "--base",
            "../outside",
            "--phase-id",
            "it005",
            "--stage-id",
            "phase-004",
            "--wave-id",
            "strict-runtime",
            "--strict-runtime",
          ].join(" "),
        },
      },
      ctx,
    );

    assert.equal(directEscapeDecision?.block, true);
    assert.match(directEscapeDecision?.reason ?? "", /tmp\/mux tree/i);

    const normalizedEscapeDecision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: [
            "uv run",
            shellQuote(path.join(MUX_TOOLS_ROOT, "session.py")),
            "normalized-base",
            "--base",
            "tmp/mux/../outside",
            "--phase-id",
            "it005",
            "--stage-id",
            "phase-004",
            "--wave-id",
            "strict-runtime",
            "--strict-runtime",
          ].join(" "),
        },
      },
      ctx,
    );

    assert.equal(normalizedEscapeDecision?.block, true);
    assert.match(normalizedEscapeDecision?.reason ?? "", /tmp\/mux tree/i);
  } finally {
    await cleanupWorkspace(workspace);
  }
});


test("strict bootstrap fails closed on chaining and basename-only spoofing before activation exists", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-bootstrap-fail-closed");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);

    const chainedDecision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: `uv run ${shellQuote(path.join(MUX_TOOLS_ROOT, "session.py"))} bootstrap-chain --phase-id it005 --stage-id phase-004 --wave-id strict-runtime --strict-runtime && echo bypass`,
        },
      },
      ctx,
    );
    assert.equal(chainedDecision?.block, true);
    assert.match(chainedDecision?.reason ?? "", /without shell operators or redirections/i);

    const basenameDecision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: "uv run session.py bootstrap-base --phase-id it005 --stage-id phase-004 --wave-id strict-runtime --strict-runtime",
        },
      },
      ctx,
    );
    assert.equal(basenameDecision?.block, true);
    assert.match(basenameDecision?.reason ?? "", /basename-only mux tool invocations are not allowed/i);
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict bash guard rejects shell chaining, backgrounding, and basename-only bypasses", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-bash-guard");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    await bootstrapStrictSession(toolCallHandler, ctx, workspace, "bash-guard");

    const chainedDecision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: `uv run ${shellQuote(path.join(MUX_TOOLS_ROOT, "signal.py"))} tmp/mux-smoke/demo/.signals/demo.done --path reports/demo.md --status success && echo bypass`,
        },
      },
      ctx,
    );
    assert.equal(chainedDecision?.block, true);
    assert.match(chainedDecision?.reason ?? "", /without shell operators or redirections/i);

    const backgroundDecision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: `uv run ${shellQuote(path.join(MUX_TOOLS_ROOT, "signal.py"))} tmp/mux-smoke/demo/.signals/demo.done --path reports/demo.md --status success &`,
        },
      },
      ctx,
    );
    assert.equal(backgroundDecision?.block, true);
    assert.match(backgroundDecision?.reason ?? "", /without shell operators or redirections/i);

    const basenameDecision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: "uv run signal.py tmp/mux-smoke/demo/.signals/demo.done --path reports/demo.md --status success",
        },
      },
      ctx,
    );
    assert.equal(basenameDecision?.block, true);
    assert.match(basenameDecision?.reason ?? "", /basename-only mux tool invocations are not allowed/i);
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict mode blocks coordinator writes outside bounded orchestration paths", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-write-block");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "write-block");

    const blocked = await toolCallHandler(
      {
        toolName: "write",
        input: { path: "src/app.py", content: "print('blocked')\n" },
      },
      ctx,
    );
    assert.equal(blocked?.block, true);
    assert.match(blocked?.reason ?? "", /outside the bounded orchestration paths/i);

    const blockedLedger = await toolCallHandler(
      {
        toolName: "write",
        input: { path: `${bootstrap.sessionDir}/.mux-ledger.json`, content: "{}\n" },
      },
      ctx,
    );
    assert.equal(blockedLedger?.block, true);
    assert.match(blockedLedger?.reason ?? "", /outside the bounded orchestration paths/i);

    const blockedActivation = await toolCallHandler(
      {
        toolName: "write",
        input: { path: path.relative(workspace, bootstrap.activationFile), content: "{}\n" },
      },
      ctx,
    );
    assert.equal(blockedActivation?.block, true);
    assert.match(blockedActivation?.reason ?? "", /outside the bounded orchestration paths/i);

    const blockedRegistry = await toolCallHandler(
      {
        toolName: "write",
        input: { path: path.relative(workspace, bootstrap.registryPath), content: "{}\n" },
      },
      ctx,
    );
    assert.equal(blockedRegistry?.block, true);
    assert.match(blockedRegistry?.reason ?? "", /outside the bounded orchestration paths/i);

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


test("strict mode fails closed on tampered activation registry paths", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-tampered-registry");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "tampered-registry");

    const registry = JSON.parse(await readFile(bootstrap.registryPath, "utf8"));
    registry.activation_file = "../outside.json";
    await writeFile(bootstrap.registryPath, `${JSON.stringify(registry, null, 2)}\n`, "utf8");

    const result = await toolCallHandler(
      {
        toolName: "write",
        input: { path: ".specs/specs/demo.md", content: "# blocked\n" },
      },
      ctx,
    );

    assert.equal(result?.block, true);
    assert.match(result?.reason ?? "", /activation_file must stay within the active session directory/i);
  } finally {
    await cleanupWorkspace(workspace);
  }
});


test("strict bash tool invocations stay within the active session and bounded control-plane contract", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-bash-paths");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "bash-paths");

    const signalDecision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: `uv run ${shellQuote(path.join(MUX_TOOLS_ROOT, "signal.py"))} ${shellQuote(`${bootstrap.sessionDir}/.signals/demo.done`)} --path reports/demo.md --status success`,
        },
      },
      ctx,
    );
    assert.equal(signalDecision?.block, true);
    assert.match(signalDecision?.reason ?? "", /signal\.py is a worker\/data-plane tool/i);

    const extractDecision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: `uv run ${shellQuote(path.join(MUX_TOOLS_ROOT, "extract-summary.py"))} ${shellQuote(`${bootstrap.sessionDir}/research/demo.md`)} --evidence --evidence-path outside-summary.json`,
        },
      },
      ctx,
    );
    assert.equal(extractDecision?.block, true);
    assert.match(extractDecision?.reason ?? "", /evidence output must stay within the active strict session directory/i);
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict bash ledger declare rejects traversal paths", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-declare-paths");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "declare-paths");

    runLedgerCommand(workspace, "prerequisites", bootstrap.sessionDir, "--required", "phase-target", "--status", "ready");
    runLedgerCommand(workspace, "transition", bootstrap.sessionDir, "--to", "RESOLVE", "--reason", "phase target persisted");
    runLedgerCommand(workspace, "transition", bootstrap.sessionDir, "--to", "DECLARE", "--reason", "prerequisites evaluated");

    const decision = await toolCallHandler(
      {
        toolName: "bash",
        input: {
          command: [
            "uv run",
            shellQuote(path.join(MUX_TOOLS_ROOT, "ledger.py")),
            "declare",
            shellQuote(bootstrap.sessionDir),
            "--worker-type",
            "worker",
            "--objective",
            shellQuote("implement approved bounded change"),
            "--scope",
            shellQuote("phase-004 approved files only"),
            "--report-path",
            shellQuote("../outside-report.md"),
            "--signal-path",
            shellQuote(`${bootstrap.sessionDir}/.signals/strict-worker.done`),
            "--expected-artifact",
            "report",
            "--expected-artifact",
            "signal",
            "--expected-artifact",
            "summary",
          ].join(" "),
        },
      },
      ctx,
    );

    assert.equal(decision?.block, true);
    assert.match(decision?.reason ?? "", /report_path must stay within the project root/i);
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

test("strict mode fails closed on unsupported single-dispatch input fields", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-input-shape");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "input-shape");

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
        input: { agent: "worker", task, cwd: workspace },
      },
      ctx,
    );

    assert.equal(decision?.block, true);
    assert.match(decision?.reason ?? "", /unsupported input field\(s\): cwd/i);

    const ledger = await readLedger(workspace, bootstrap.sessionDir);
    assert.equal(ledger.control_state, "DECLARE");
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict mode validates declared expected artifacts in task contract", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-expected-artifacts");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "expected-artifacts");

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
      "--expected-artifact",
      "audit",
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

    assert.equal(decision?.block, true);
    assert.match(decision?.reason ?? "", /expected_artifacts contains unsupported artifact: audit/i);

    const ledger = await readLedger(workspace, bootstrap.sessionDir);
    assert.equal(ledger.control_state, "DECLARE");
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
    assert.match(decision?.reason ?? "", /missing the declared signal artifact path|missing the no-nested-subagents rule/i);
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

test("strict deactivate re-entry is a no-op", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-deactivate-reentry");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    await bootstrapStrictSession(toolCallHandler, ctx, workspace, "deactivate-reentry");

    const deactivateEvent = {
      toolName: "bash",
      input: {
        command: `uv run ${shellQuote(path.join(MUX_TOOLS_ROOT, "deactivate.py"))}`,
      },
    };

    const firstDecision = await toolCallHandler(deactivateEvent, ctx);
    assert.equal(firstDecision, undefined);

    const firstResult = runShell(deactivateEvent.input.command, workspace);
    assert.equal(firstResult.status, 0, firstResult.stdout + firstResult.stderr);
    assert.equal(parseOutputValue(firstResult.stdout, "STRICT_RUNTIME_DEACTIVATED"), "true");

    const secondDecision = await toolCallHandler(deactivateEvent, ctx);
    assert.equal(secondDecision, undefined);

    const secondResult = runShell(deactivateEvent.input.command, workspace);
    assert.equal(secondResult.status, 0, secondResult.stdout + secondResult.stderr);
    assert.equal(parseOutputValue(secondResult.stdout, "STRICT_RUNTIME_DEACTIVATED"), "false");
  } finally {
    await cleanupWorkspace(workspace);
  }
});

test("strict ledger rejects illegal ADVANCE->ADVANCE transition", async () => {
  const workspace = await createWorkspace("strict-mux-runtime-illegal-advancement");
  try {
    const { toolCallHandler } = createRuntime();
    const ctx = createContext(workspace);
    const bootstrap = await bootstrapStrictSession(toolCallHandler, ctx, workspace, "illegal-advancement");

    const reportPath = "reports/illegal-adv-worker.md";
    const signalPath = `${bootstrap.sessionDir}/.signals/illegal-adv-worker.done`;
    const summaryEvidencePath = `${bootstrap.sessionDir}/research/illegal-adv-summary.json`;
    const objective = "implement approved bounded change";
    const scope = "phase-008 regression tests";

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

    const dispatchDecision = await toolCallHandler(
      {
        toolName: "subagent",
        input: { agent: "worker", task },
      },
      ctx,
    );
    assert.equal(dispatchDecision, undefined);

    await writeWorkerReport(workspace, reportPath);
    emitSuccessSignal(workspace, signalPath, reportPath);
    emitSummaryEvidence(workspace, reportPath, summaryEvidencePath);

    const gateResult = runVerifyGate(workspace, bootstrap.sessionDir, summaryEvidencePath);
    assert.equal(gateResult.status, 0, gateResult.stdout + gateResult.stderr);

    let ledger = await readLedger(workspace, bootstrap.sessionDir);
    assert.equal(ledger.control_state, "ADVANCE");

    const advanceTransitionResult = runShell(
      [
        "uv run",
        shellQuote(path.join(MUX_TOOLS_ROOT, "ledger.py")),
        "transition",
        shellQuote(bootstrap.sessionDir),
        "--to",
        "ADVANCE",
        "--reason",
        shellQuote("attempt bypass: ADVANCE->ADVANCE"),
      ].join(" "),
      workspace,
    );

    assert.notEqual(advanceTransitionResult.status, 0);
    assert.match(String(advanceTransitionResult.stderr), /Illegal transition/i);

    ledger = await readLedger(workspace, bootstrap.sessionDir);
    assert.equal(ledger.control_state, "ADVANCE");
  } finally {
    await cleanupWorkspace(workspace);
  }
});
