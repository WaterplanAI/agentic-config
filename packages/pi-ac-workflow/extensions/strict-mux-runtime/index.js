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
]);
const ALLOWED_MUX_TOOL_BASENAMES = Object.freeze([
  "session.py",
  "deactivate.py",
  "ledger.py",
  "verify.py",
  "extract-summary.py",
  "signal.py",
  "check-signals.py",
]);
const ALLOWED_MUX_TOOL_PATH_SET = new Set(
  ALLOWED_MUX_TOOL_BASENAMES.map((basename) => path.normalize(path.join(MUX_TOOLS_ROOT, basename))),
);
const STRICT_SUBAGENT_ALLOWED_INPUT_KEYS = new Set(["agent", "task"]);
const STRICT_EXPECTED_ARTIFACTS = new Set(["report", "signal", "summary"]);
const STRICT_BASH_FORBIDDEN_OPERATOR_PATTERN = /(?:&&|\|\||;|\||>|<|&|`|\$\(|\r|\n)/;

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

function normalizeCoordinatorWriteRoots(projectRoot, candidateRoots) {
  const specsRoot = resolveProjectPath(projectRoot, ".specs");
  const roots = new Set(DEFAULT_ALLOWED_WRITE_ROOTS);

  for (const value of Array.isArray(candidateRoots) ? candidateRoots : []) {
    if (typeof value !== "string" || !value.trim()) continue;
    const resolvedRoot = resolveProjectPath(projectRoot, value);
    if (!isWithinRoot(resolvedRoot, specsRoot)) continue;
    roots.add(path.relative(projectRoot, resolvedRoot) || ".specs");
  }

  return [...roots];
}

function hasSessionKeyFlag(command) {
  return new RegExp(`${escapeRegExp(SESSION_KEY_FLAG)}(?:=|\\s)`).test(String(command ?? "").replace(/\n/g, " "));
}

function injectSessionKeyFlag(command, sessionKey) {
  if (hasSessionKeyFlag(command)) return command;
  return `${String(command).trim()} ${SESSION_KEY_FLAG} ${shellQuote(sessionKey)}`;
}

function withForcedSessionKey(parsedCommand, sessionKey) {
  const filteredArgs = [];
  for (let index = 0; index < parsedCommand.args.length; index += 1) {
    const token = parsedCommand.args[index];
    if (token === SESSION_KEY_FLAG) {
      const next = parsedCommand.args[index + 1];
      if (typeof next === "string" && !next.startsWith("--")) {
        index += 1;
      }
      continue;
    }
    if (token.startsWith(`${SESSION_KEY_FLAG}=`)) {
      continue;
    }
    filteredArgs.push(token);
  }

  return ["uv", "run", parsedCommand.toolToken, ...filteredArgs, SESSION_KEY_FLAG, sessionKey]
    .map((token) => shellQuote(token))
    .join(" ");
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function splitShellWords(command) {
  const tokens = [];
  let current = "";
  let activeQuote = "";
  let escaped = false;

  for (const char of String(command ?? "")) {
    if (escaped) {
      current += char;
      escaped = false;
      continue;
    }

    if (char === "\\" && activeQuote !== "'") {
      escaped = true;
      continue;
    }

    if (activeQuote) {
      if (char === activeQuote) {
        activeQuote = "";
      } else {
        current += char;
      }
      continue;
    }

    if (char === "'" || char === '"') {
      activeQuote = char;
      continue;
    }

    if (/\s/.test(char)) {
      if (current) {
        tokens.push(current);
        current = "";
      }
      continue;
    }

    current += char;
  }

  if (escaped) {
    return { tokens: [], error: "dangling escape in bash command" };
  }
  if (activeQuote) {
    return { tokens: [], error: "unterminated quote in bash command" };
  }

  if (current) {
    tokens.push(current);
  }

  return { tokens };
}

function parseStrictMuxUvRunCommand(command, projectRoot) {
  const trimmed = String(command ?? "").trim();
  if (!trimmed) {
    return {
      allow: false,
      reason: "bash command is empty",
    };
  }

  if (STRICT_BASH_FORBIDDEN_OPERATOR_PATTERN.test(trimmed)) {
    return {
      allow: false,
      reason: "bash command must be a single `uv run <package-owned mux tool>` invocation without shell operators or redirections",
    };
  }

  const splitResult = splitShellWords(trimmed);
  if (splitResult.error) {
    return {
      allow: false,
      reason: splitResult.error,
    };
  }

  const tokens = splitResult.tokens;
  if (tokens.length < 3 || tokens[0] !== "uv" || tokens[1] !== "run") {
    return {
      allow: false,
      reason: "bash command must start with exact `uv run <package-owned mux tool>`",
    };
  }

  const toolToken = tokens[2];
  if (!/[\\/]/.test(toolToken)) {
    return {
      allow: false,
      reason: "basename-only mux tool invocations are not allowed",
    };
  }

  const resolvedToolPath = path.normalize(path.resolve(projectRoot, toolToken));
  if (!ALLOWED_MUX_TOOL_PATH_SET.has(resolvedToolPath)) {
    return {
      allow: false,
      reason: "bash command must invoke exactly one package-owned mux tool path",
    };
  }

  return {
    allow: true,
    args: tokens.slice(3),
    command: trimmed,
    toolPath: resolvedToolPath,
    toolBasename: path.basename(resolvedToolPath),
    toolToken,
  };
}

function getFlagValue(args, flagName) {
  for (let index = 0; index < args.length; index += 1) {
    const token = args[index];
    if (token === flagName) {
      const next = args[index + 1];
      return typeof next === "string" ? next : undefined;
    }
    if (token.startsWith(`${flagName}=`)) {
      return token.slice(flagName.length + 1);
    }
  }
  return undefined;
}

function getPositionals(args) {
  const positionals = [];
  for (let index = 0; index < args.length; index += 1) {
    const token = args[index];
    if (token.startsWith("--")) {
      if (!token.includes("=")) {
        const next = args[index + 1];
        if (typeof next === "string" && !next.startsWith("--")) {
          index += 1;
        }
      }
      continue;
    }
    positionals.push(token);
  }
  return positionals;
}

function isRelativePathWithin(projectRoot, candidatePath, allowedRoot) {
  if (typeof candidatePath !== "string" || !candidatePath.trim()) return false;
  if (path.isAbsolute(candidatePath)) return false;
  return isWithinRoot(
    resolveProjectPath(projectRoot, candidatePath),
    resolveProjectPath(projectRoot, allowedRoot),
  );
}

function isDeclaredReportPath(ledger, candidatePath) {
  return typeof ledger?.declared_dispatch?.report_path === "string"
    && ledger.declared_dispatch.report_path === candidatePath;
}

function validateStrictBootstrapCommand(parsedCommand) {
  const basePath = getFlagValue(parsedCommand.args, "--base") ?? "tmp/mux";
  if (path.isAbsolute(basePath)) {
    return {
      allow: false,
      reason: "session.py strict bootstrap must keep --base within the project-local tmp/mux tree",
    };
  }

  const normalizedBase = path.posix.normalize(basePath.replace(/\\/g, "/"));
  if (!(normalizedBase === "tmp/mux" || normalizedBase.startsWith("tmp/mux/"))) {
    return {
      allow: false,
      reason: "session.py strict bootstrap must keep --base within the project-local tmp/mux tree",
    };
  }

  return { allow: true, command: parsedCommand.command };
}

function validateStrictBashToolInvocation(parsedCommand, activation, ledger, projectRoot) {
  const positionals = getPositionals(parsedCommand.args);

  if (parsedCommand.toolBasename === "session.py") {
    return {
      allow: false,
      reason: "session.py bootstrap is only allowed before strict activation is established",
    };
  }

  if (parsedCommand.toolBasename === "deactivate.py") {
    return { allow: true, command: parsedCommand.command };
  }

  if (parsedCommand.toolBasename === "signal.py") {
    return {
      allow: false,
      reason: "signal.py is a worker/data-plane tool and is not allowed for strict coordinators",
    };
  }

  if (parsedCommand.toolBasename === "check-signals.py") {
    if (positionals[0] !== activation.session_dir) {
      return {
        allow: false,
        reason: "check-signals.py must target the active strict session directory",
      };
    }
    return { allow: true, command: parsedCommand.command };
  }

  if (parsedCommand.toolBasename === "verify.py") {
    if (positionals[0] !== activation.session_dir) {
      return {
        allow: false,
        reason: "verify.py must target the active strict session directory",
      };
    }

    const summaryEvidencePath = getFlagValue(parsedCommand.args, "--summary-evidence");
    if (summaryEvidencePath && !isRelativePathWithin(projectRoot, summaryEvidencePath, activation.session_dir)) {
      return {
        allow: false,
        reason: "verify.py summary evidence must stay within the active strict session directory",
      };
    }
    return { allow: true, command: parsedCommand.command };
  }

  if (parsedCommand.toolBasename === "extract-summary.py") {
    const reportPath = positionals[0];
    if (!reportPath) {
      return {
        allow: false,
        reason: "extract-summary.py requires a declared report path",
      };
    }
    if (!isRelativePathWithin(projectRoot, reportPath, ".")) {
      return {
        allow: false,
        reason: "extract-summary.py report path must stay within the project root",
      };
    }
    if (!isDeclaredReportPath(ledger, reportPath) && !isRelativePathWithin(projectRoot, reportPath, activation.session_dir)) {
      return {
        allow: false,
        reason: "extract-summary.py must target the declared report or a report within the active strict session directory",
      };
    }

    const evidencePath = getFlagValue(parsedCommand.args, "--evidence-path");
    if (evidencePath && !isRelativePathWithin(projectRoot, evidencePath, activation.session_dir)) {
      return {
        allow: false,
        reason: "extract-summary.py evidence output must stay within the active strict session directory",
      };
    }
    return { allow: true, command: parsedCommand.command };
  }

  if (parsedCommand.toolBasename === "ledger.py") {
    const subcommand = positionals[0];
    const sessionDir = positionals[1];
    if (sessionDir !== activation.session_dir) {
      return {
        allow: false,
        reason: "ledger.py must target the active strict session directory",
      };
    }

    if (subcommand === "show" || subcommand === "prerequisites") {
      return { allow: true, command: parsedCommand.command };
    }

    if (subcommand === "declare") {
      if (ledger.control_state !== "DECLARE") {
        return {
          allow: false,
          reason: `ledger.py declare requires control_state=DECLARE, found ${String(ledger.control_state ?? "")}`,
        };
      }

      const reportPath = getFlagValue(parsedCommand.args, "--report-path");
      const signalPath = getFlagValue(parsedCommand.args, "--signal-path");
      if (!isRelativePathWithin(projectRoot, reportPath, ".")) {
        return {
          allow: false,
          reason: "ledger.py declare report_path must stay within the project root",
        };
      }
      if (!isRelativePathWithin(projectRoot, signalPath, ".")) {
        return {
          allow: false,
          reason: "ledger.py declare signal_path must stay within the project root",
        };
      }
      return { allow: true, command: parsedCommand.command };
    }

    if (subcommand === "transition") {
      const toState = getFlagValue(parsedCommand.args, "--to");
      const currentState = String(ledger.control_state ?? "");
      const transitionAllowed = (
        (currentState === "LOCK" && toState === "RESOLVE")
        || (currentState === "RESOLVE" && toState === "DECLARE")
        || ((currentState === "BLOCK" || currentState === "RECOVER") && toState === "RESOLVE")
      );
      if (!transitionAllowed) {
        return {
          allow: false,
          reason: `ledger.py transition to ${String(toState ?? "") || "<missing>"} is not allowed from control_state=${currentState}`,
        };
      }
      return { allow: true, command: parsedCommand.command };
    }

    if (["blocker-open", "blocker-clear", "recovery-start", "recovery-complete"].includes(subcommand)) {
      return { allow: true, command: parsedCommand.command };
    }

    return {
      allow: false,
      reason: `ledger.py subcommand ${String(subcommand ?? "<missing>")} is not allowed under strict coordinator mode`,
    };
  }

  return {
    allow: false,
    reason: `mux tool ${parsedCommand.toolBasename} is not allowed under strict coordinator mode`,
  };
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
  if (!isRelativePathWithin(projectRoot, activation.session_dir, ".")) {
    throw new Error("Strict runtime activation session_dir must stay within the project root");
  }
  if (!isRelativePathWithin(projectRoot, activation.ledger_path, activation.session_dir)) {
    throw new Error("Strict runtime activation ledger_path must stay within the active session directory");
  }
  if (!isRelativePathWithin(projectRoot, activation.activation_file, activation.session_dir)) {
    throw new Error("Strict runtime activation activation_file must stay within the active session directory");
  }

  const activationFilePath = resolveProjectPath(projectRoot, activation.activation_file);
  if (!(await pathExists(activationFilePath))) {
    throw new Error("Strict runtime activation_file does not exist");
  }
  const activationFilePayload = await readJsonFile(activationFilePath);
  if (!activationFilePayload || typeof activationFilePayload !== "object") {
    throw new Error("Strict runtime activation_file is not a JSON object");
  }
  if (activationFilePayload.session_key !== sessionKey) {
    throw new Error("Strict runtime activation_file session_key does not match the current pi session");
  }
  if (activationFilePayload.session_key_hash !== hashSessionKey(sessionKey)) {
    throw new Error("Strict runtime activation_file session_key_hash does not match the current pi session");
  }
  if (activationFilePayload.session_dir !== activation.session_dir) {
    throw new Error("Strict runtime activation_file session_dir does not match the session registry");
  }
  if (activationFilePayload.ledger_path !== activation.ledger_path) {
    throw new Error("Strict runtime activation_file ledger_path does not match the session registry");
  }
  if (activationFilePayload.activation_file !== activation.activation_file) {
    throw new Error("Strict runtime activation_file path does not match the session registry");
  }

  return {
    ...activation,
    registry_path: path.relative(projectRoot, registryPath) || path.basename(registryPath),
    allowed_write_roots: normalizeCoordinatorWriteRoots(projectRoot, DEFAULT_ALLOWED_WRITE_ROOTS),
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

function normalizeExpectedArtifacts(expectedArtifacts) {
  if (!Array.isArray(expectedArtifacts)) {
    return [];
  }

  return [...new Set(
    expectedArtifacts
      .filter((artifact) => typeof artifact === "string" && artifact.trim())
      .map((artifact) => artifact.trim().toLowerCase()),
  )];
}

function validateStrictSubagentTask(task, declaredDispatch) {
  const issues = [];
  const taskText = String(task ?? "");
  const normalizedTask = collapseWhitespace(taskText);
  const normalizedTaskPathText = taskText.replace(/\\/g, "/");
  const protocolReferencePresent = /assets\/mux\/protocol\/subagent\.md/i.test(normalizedTaskPathText);

  if (!normalizedTask.includes(collapseWhitespace(declaredDispatch.objective))) {
    issues.push("task is missing the declared objective");
  }
  if (!normalizedTask.includes(collapseWhitespace(declaredDispatch.scope))) {
    issues.push("task is missing the declared scope boundary");
  }
  if (!protocolReferencePresent) {
    issues.push("task is missing the mux subagent protocol reference");
  }
  if (declaredDispatch.no_nested_subagents !== true) {
    issues.push("declared_dispatch.no_nested_subagents must be true");
  }
  if (!/no nested subagents/i.test(taskText)) {
    issues.push("task is missing the no-nested-subagents rule");
  }
  if (!/return exactly\s+`?0`?\s+on success/i.test(taskText)) {
    issues.push("task is missing the exact `0` success rule");
  }

  const expectedArtifacts = normalizeExpectedArtifacts(declaredDispatch.expected_artifacts);
  if (expectedArtifacts.length === 0) {
    issues.push("declared_dispatch.expected_artifacts must declare at least one artifact");
  }

  for (const artifact of expectedArtifacts) {
    if (!STRICT_EXPECTED_ARTIFACTS.has(artifact)) {
      issues.push(`declared_dispatch.expected_artifacts contains unsupported artifact: ${artifact}`);
      continue;
    }

    if (artifact === "report" && !taskText.includes(declaredDispatch.report_path)) {
      issues.push("task is missing the declared report artifact path");
      continue;
    }

    if (artifact === "signal" && !taskText.includes(declaredDispatch.signal_path)) {
      issues.push("task is missing the declared signal artifact path");
      continue;
    }

    if (artifact === "summary") {
      const summaryContractPresent = /executive summary/i.test(taskText) || protocolReferencePresent;
      if (!summaryContractPresent) {
        issues.push("task is missing the declared summary artifact contract");
      }
    }
  }

  return issues;
}

function buildStrictViolation(reason) {
  return {
    block: true,
    reason: `Strict MUX violation: ${reason}`,
  };
}

function getStrictBashDecision(command, sessionKey, projectRoot, activation, ledger, parsedCommand) {
  const parsed = parsedCommand ?? parseStrictMuxUvRunCommand(command, projectRoot);
  if (!parsed.allow) {
    return parsed;
  }

  if (parsed.toolBasename === "deactivate.py") {
    return {
      allow: true,
      command: withForcedSessionKey(parsed, sessionKey),
      toolBasename: parsed.toolBasename,
    };
  }

  return validateStrictBashToolInvocation(parsed, activation, ledger, projectRoot);
}

async function enforceStrictSubagentCall(event, projectRoot, activation, ledger) {
  const input = event?.input;
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return buildStrictViolation("strict single-dispatch subagent input must be an object with only `agent` and `task`");
  }

  if (Object.hasOwn(input, "tasks")) {
    return buildStrictViolation("strict mode supports only single subagent dispatches; `tasks` is not allowed");
  }
  if (Object.hasOwn(input, "chain")) {
    return buildStrictViolation("strict mode supports only single subagent dispatches; `chain` is not allowed");
  }

  const unsupportedInputKeys = Object.keys(input).filter((key) => !STRICT_SUBAGENT_ALLOWED_INPUT_KEYS.has(key));
  if (unsupportedInputKeys.length > 0) {
    return buildStrictViolation(
      `strict single-dispatch supports only agent/task; unsupported input field(s): ${unsupportedInputKeys.join(", ")}`,
    );
  }

  const agent = String(input.agent ?? "").trim();
  const task = String(input.task ?? "").trim();
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
  const toolName = normalizeToolName(event?.toolName);
  const command = String(event?.input?.command ?? "");
  const sessionKey = resolveCurrentSessionKey(ctx);
  const projectRoot = resolveProjectRoot(ctx?.cwd || process.cwd());

  const parsedBashCommand = toolName === "bash"
    ? parseStrictMuxUvRunCommand(command, projectRoot)
    : undefined;
  const isStrictBootstrapAttempt = toolName === "bash"
    && command.includes(STRICT_RUNTIME_FLAG)
    && command.includes("session.py");

  if (isStrictBootstrapAttempt) {
    if (!parsedBashCommand?.allow || parsedBashCommand.toolBasename !== "session.py") {
      return buildStrictViolation(parsedBashCommand?.reason ?? "strict bootstrap must use the exact package-owned session.py path");
    }

    const bootstrapDecision = validateStrictBootstrapCommand(parsedBashCommand);
    if (!bootstrapDecision.allow) {
      return buildStrictViolation(bootstrapDecision.reason);
    }

    let existingActivation;
    try {
      existingActivation = await readStrictRuntimeActivation(projectRoot, sessionKey);
    } catch (error) {
      return buildStrictViolation(error instanceof Error ? error.message : String(error));
    }

    if (existingActivation) {
      return buildStrictViolation("session.py strict bootstrap is only allowed before strict activation is established for the current session; run deactivate.py first");
    }

    event.input.command = withForcedSessionKey(parsedBashCommand, sessionKey);
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

  if (
    toolName === "bash"
    && parsedBashCommand?.allow
    && parsedBashCommand.toolBasename === "deactivate.py"
  ) {
    event.input.command = withForcedSessionKey(parsedBashCommand, sessionKey);
    return undefined;
  }

  let ledger;
  try {
    ledger = await loadStrictLedger(projectRoot, activation.session_dir);
  } catch (error) {
    return buildStrictViolation(error instanceof Error ? error.message : String(error));
  }

  if (toolName === "bash") {
    const decision = getStrictBashDecision(command, sessionKey, projectRoot, activation, ledger, parsedBashCommand);
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
