import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { promises as fs, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const MUX_TOOLS_ROOT = path.join(PACKAGE_ROOT, "assets", "mux", "tools");
const STRICT_RUNTIME_VERSION = 1;
const STRICT_RUNTIME_REGISTRY_DIR = path.join("outputs", "session", "mux-runtime");
const SESSION_KEY_FLAG = "--session-key";
const STRICT_RUNTIME_FLAG = "--strict-runtime";
const STRICT_RUNTIME_TOOL_NAME = "strict-mux-runtime";
const DEFAULT_ALLOWED_WRITE_ROOTS = Object.freeze([
  ".specs",
  STRICT_RUNTIME_REGISTRY_DIR,
]);
const ALLOWED_MUX_TOOL_BASENAMES = new Set([
  "session.py",
  "deactivate.py",
  "ledger.py",
  "verify.py",
  "extract-summary.py",
  "signal.py",
  "check-signals.py",
]);

function normalizeToolName(toolName) {
  return String(toolName ?? "").trim().toLowerCase();
}

function collapseWhitespace(text) {
  return String(text ?? "").replace(/\s+/g, " ").trim().toLowerCase();
}

function hashSessionKey(sessionKey) {
  return createHash("sha256").update(sessionKey, "utf8").digest("hex").slice(0, 24);
}

function resolveProjectRoot(startPath) {
  let current = path.resolve(startPath || process.cwd());
  for (let depth = 0; depth < 10; depth += 1) {
    if (existsSync(path.join(current, ".git")) || existsSync(path.join(current, "CLAUDE.md"))) {
      return current;
    }
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return path.resolve(startPath || process.cwd());
}

function existsSync(filePath) {
  try {
    return Boolean(filePath) && Boolean(statSync(filePath));
  } catch {
    return false;
  }
}

function resolveCurrentSessionKey(ctx) {
  const sessionFile = ctx?.sessionManager?.getSessionFile?.();
  if (typeof sessionFile === "string" && sessionFile.trim()) {
    return `session-file:${path.resolve(sessionFile.trim())}`;
  }

  const sessionId = ctx?.sessionManager?.getSessionId?.();
  if (typeof sessionId === "string" && sessionId.trim()) {
    return `session-id:${sessionId.trim()}`;
  }

  return `ephemeral:${path.resolve(ctx?.cwd || process.cwd())}`;
}

function getStrictRuntimeRegistryPath(projectRoot, sessionKey) {
  return path.join(projectRoot, STRICT_RUNTIME_REGISTRY_DIR, `${hashSessionKey(sessionKey)}.json`);
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `"'"'`)}'`;
}

function resolveProjectPath(projectRoot, candidatePath) {
  if (!candidatePath) return projectRoot;
  return path.resolve(projectRoot, candidatePath);
}

function isWithinRoot(candidatePath, rootPath) {
  const relative = path.relative(rootPath, candidatePath);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function hasSessionKeyFlag(command) {
  return new RegExp(`${escapeRegExp(SESSION_KEY_FLAG)}(?:=|\s)`).test(String(command ?? "").replace(/\n/g, " "));
}

function injectSessionKeyFlag(command, sessionKey) {
  if (hasSessionKeyFlag(command)) return command;
  return `${String(command).trim()} ${SESSION_KEY_FLAG} ${shellQuote(sessionKey)}`;
}

function isUvRunMuxToolCommand(command, basename) {
  return /\buv\s+run\b/.test(command)
    && new RegExp(`(?:^|[\\/])${escapeRegExp(basename)}(?:["'\\s]|$)`).test(command);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function isStrictSessionBootstrapCommand(command) {
  return isUvRunMuxToolCommand(command, "session.py") && command.includes(STRICT_RUNTIME_FLAG);
}

function isDeactivateCommand(command) {
  return isUvRunMuxToolCommand(command, "deactivate.py");
}

async function pathExists(filePath) {
  try {
    await fs.stat(filePath);
    return true;
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return false;
    }
    throw error;
  }
}

async function readJsonFile(filePath) {
  return JSON.parse(await fs.readFile(filePath, "utf8"));
}

async function runCommand(command, args, cwd) {
  return await new Promise((resolve, reject) => {
    const proc = spawn(command, args, {
      cwd,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    proc.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("error", reject);
    proc.on("close", (code) => {
      resolve({ code: code ?? 1, stdout, stderr });
    });
  });
}

async function readStrictRuntimeActivation(projectRoot, sessionKey) {
  const registryPath = getStrictRuntimeRegistryPath(projectRoot, sessionKey);
  if (!(await pathExists(registryPath))) return undefined;

  const payload = await readJsonFile(registryPath);
  if (!payload || typeof payload !== "object") {
    throw new Error(`Strict runtime registry is not a JSON object: ${registryPath}`);
  }

  const activation = payload;
  if (activation.version !== STRICT_RUNTIME_VERSION) {
    throw new Error(`Unsupported strict runtime activation version: ${activation.version}`);
  }
  if (activation.mode !== "strict") {
    throw new Error(`Unsupported strict runtime mode: ${String(activation.mode ?? "")}`);
  }
  if (activation.session_key !== sessionKey) {
    throw new Error("Strict runtime activation session key does not match the current pi session");
  }
  if (activation.session_key_hash !== hashSessionKey(sessionKey)) {
    throw new Error("Strict runtime activation session key hash does not match the current pi session");
  }
  if (typeof activation.session_dir !== "string" || !activation.session_dir.trim()) {
    throw new Error("Strict runtime activation is missing session_dir");
  }
  if (typeof activation.ledger_path !== "string" || !activation.ledger_path.trim()) {
    throw new Error("Strict runtime activation is missing ledger_path");
  }
  if (typeof activation.activation_file !== "string" || !activation.activation_file.trim()) {
    throw new Error("Strict runtime activation is missing activation_file");
  }

  const allowedWriteRoots = Array.isArray(activation.allowed_write_roots)
    ? activation.allowed_write_roots.filter((value) => typeof value === "string" && value.trim())
    : [];

  return {
    ...activation,
    registry_path: path.relative(projectRoot, registryPath) || path.basename(registryPath),
    allowed_write_roots: [...new Set([...DEFAULT_ALLOWED_WRITE_ROOTS, ...allowedWriteRoots])],
  };
}

async function loadStrictLedger(projectRoot, sessionDir) {
  const ledgerToolPath = path.join(MUX_TOOLS_ROOT, "ledger.py");
  const result = await runCommand("uv", ["run", ledgerToolPath, "show", sessionDir], projectRoot);
  if (result.code !== 0) {
    throw new Error(result.stderr.trim() || result.stdout.trim() || "Unable to load mux ledger");
  }

  try {
    const payload = JSON.parse(result.stdout);
    if (!payload || typeof payload !== "object") {
      throw new Error("Ledger payload is not a JSON object");
    }
    return payload;
  } catch (error) {
    throw new Error(`Unable to parse mux ledger JSON: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function transitionLedgerToDispatch(projectRoot, sessionDir) {
  const ledgerToolPath = path.join(MUX_TOOLS_ROOT, "ledger.py");
  const result = await runCommand(
    "uv",
    [
      "run",
      ledgerToolPath,
      "transition",
      sessionDir,
      "--to",
      "DISPATCH",
      "--reason",
      "strict runtime validated declared dispatch",
      "--actor",
      STRICT_RUNTIME_TOOL_NAME,
    ],
    projectRoot,
  );
  if (result.code !== 0) {
    throw new Error(result.stderr.trim() || result.stdout.trim() || "Unable to transition mux ledger to DISPATCH");
  }
  return result.stdout;
}

function getWritePathFromEvent(event) {
  const toolName = normalizeToolName(event?.toolName);
  if (toolName === "write" || toolName === "edit") {
    return event?.input?.path;
  }
  if (toolName === "notebookedit") {
    return event?.input?.notebook_path;
  }
  return undefined;
}

function isAllowedCoordinatorWritePath(projectRoot, activation, candidatePath) {
  if (typeof candidatePath !== "string" || !candidatePath.trim()) return false;
  const absoluteCandidate = resolveProjectPath(projectRoot, candidatePath);
  return activation.allowed_write_roots.some((rootPath) => {
    if (typeof rootPath !== "string" || !rootPath.trim()) return false;
    return isWithinRoot(absoluteCandidate, resolveProjectPath(projectRoot, rootPath));
  });
}

function validateStrictSubagentTask(task, declaredDispatch) {
  const issues = [];
  const taskText = String(task ?? "");
  const normalizedTask = collapseWhitespace(taskText);

  if (!normalizedTask.includes(collapseWhitespace(declaredDispatch.objective))) {
    issues.push("task is missing the declared objective");
  }
  if (!normalizedTask.includes(collapseWhitespace(declaredDispatch.scope))) {
    issues.push("task is missing the declared scope boundary");
  }
  if (!taskText.includes(declaredDispatch.report_path)) {
    issues.push("task is missing the declared report path");
  }
  if (!taskText.includes(declaredDispatch.signal_path)) {
    issues.push("task is missing the declared signal path");
  }
  if (!/assets\/mux\/protocol\/subagent\.md/i.test(taskText.replace(/\\/g, "/"))) {
    issues.push("task is missing the mux subagent protocol reference");
  }
  if (!/no nested subagents/i.test(taskText)) {
    issues.push("task is missing the no-nested-subagents rule");
  }
  if (!/return exactly\s+`?0`?\s+on success/i.test(taskText)) {
    issues.push("task is missing the exact `0` success rule");
  }

  return issues;
}

function buildStrictViolation(reason) {
  return {
    block: true,
    reason: `Strict MUX violation: ${reason}`,
  };
}

function getStrictBashDecision(command, sessionKey, activation) {
  if (isStrictSessionBootstrapCommand(command)) {
    return {
      allow: true,
      command: injectSessionKeyFlag(command, sessionKey),
    };
  }

  if (isDeactivateCommand(command)) {
    return {
      allow: true,
      command: injectSessionKeyFlag(command, sessionKey),
    };
  }

  for (const basename of ALLOWED_MUX_TOOL_BASENAMES) {
    if (isUvRunMuxToolCommand(command, basename)) {
      return { allow: true, command };
    }
  }

  const trimmed = String(command ?? "").trim();
  if (/^mkdir\s+-p\s+/.test(trimmed)) {
    const allowedRoots = [activation.session_dir, ...activation.allowed_write_roots].filter(Boolean);
    if (allowedRoots.some((rootPath) => trimmed.includes(rootPath))) {
      return { allow: true, command };
    }
  }

  return {
    allow: false,
    reason: "bash command is outside the bounded mux control-plane allowlist",
  };
}

async function enforceStrictSubagentCall(event, projectRoot, activation, ledger) {
  if (Array.isArray(event?.input?.tasks) && event.input.tasks.length > 0) {
    return buildStrictViolation("strict mode supports only single subagent dispatches; `tasks` is not allowed");
  }
  if (Array.isArray(event?.input?.chain) && event.input.chain.length > 0) {
    return buildStrictViolation("strict mode supports only single subagent dispatches; `chain` is not allowed");
  }

  const agent = String(event?.input?.agent ?? "").trim();
  const task = String(event?.input?.task ?? "").trim();
  if (!agent) {
    return buildStrictViolation("single strict subagent dispatch requires `agent`");
  }
  if (!task) {
    return buildStrictViolation("single strict subagent dispatch requires `task`");
  }

  if (ledger.control_state !== "DECLARE") {
    return buildStrictViolation(`subagent dispatch requires control_state=DECLARE, found ${String(ledger.control_state ?? "")}`);
  }

  const declaredDispatch = ledger?.declared_dispatch;
  if (!declaredDispatch || typeof declaredDispatch !== "object") {
    return buildStrictViolation("declared_dispatch is missing from the strict mux ledger");
  }
  if (agent !== declaredDispatch.worker_type) {
    return buildStrictViolation(`subagent agent ${agent} does not match declared worker_type ${String(declaredDispatch.worker_type ?? "")}`);
  }

  const taskIssues = validateStrictSubagentTask(task, declaredDispatch);
  if (taskIssues.length > 0) {
    return buildStrictViolation(taskIssues.join("; "));
  }

  try {
    await transitionLedgerToDispatch(projectRoot, activation.session_dir);
  } catch (error) {
    return buildStrictViolation(error instanceof Error ? error.message : String(error));
  }

  return undefined;
}

async function evaluateStrictMuxToolCall(event, ctx) {
  const command = String(event?.input?.command ?? "");
  const sessionKey = resolveCurrentSessionKey(ctx);
  const projectRoot = resolveProjectRoot(ctx?.cwd || process.cwd());

  if (normalizeToolName(event?.toolName) === "bash" && isStrictSessionBootstrapCommand(command)) {
    event.input.command = injectSessionKeyFlag(command, sessionKey);
    return undefined;
  }

  let activation;
  try {
    activation = await readStrictRuntimeActivation(projectRoot, sessionKey);
  } catch (error) {
    return buildStrictViolation(error instanceof Error ? error.message : String(error));
  }

  if (!activation) {
    return undefined;
  }

  if (normalizeToolName(event?.toolName) === "bash" && isDeactivateCommand(command)) {
    event.input.command = injectSessionKeyFlag(command, sessionKey);
    return undefined;
  }

  let ledger;
  try {
    ledger = await loadStrictLedger(projectRoot, activation.session_dir);
  } catch (error) {
    return buildStrictViolation(error instanceof Error ? error.message : String(error));
  }

  const toolName = normalizeToolName(event?.toolName);

  if (toolName === "bash") {
    const decision = getStrictBashDecision(command, sessionKey, activation);
    if (!decision.allow) {
      return buildStrictViolation(decision.reason);
    }
    event.input.command = decision.command;
    return undefined;
  }

  if (toolName === "subagent") {
    return await enforceStrictSubagentCall(event, projectRoot, activation, ledger);
  }

  if (toolName === "write" || toolName === "edit" || toolName === "notebookedit") {
    const candidatePath = getWritePathFromEvent(event);
    if (isAllowedCoordinatorWritePath(projectRoot, activation, candidatePath)) {
      return undefined;
    }
    return buildStrictViolation(
      `coordinator mutation is outside the bounded orchestration paths: ${String(candidatePath ?? "")}`,
    );
  }

  return undefined;
}

export default function registerStrictMuxRuntime(pi) {
  pi.on("tool_call", async (event, ctx) => {
    return await evaluateStrictMuxToolCall(event, ctx);
  });
}

export {
  STRICT_RUNTIME_REGISTRY_DIR,
  STRICT_RUNTIME_VERSION,
  evaluateStrictMuxToolCall,
  getStrictRuntimeRegistryPath,
  hashSessionKey,
  readStrictRuntimeActivation,
  resolveCurrentSessionKey,
  resolveProjectRoot,
  validateStrictSubagentTask,
};
