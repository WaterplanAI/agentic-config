import { normalizeSpawnCwd } from "./env.js";
import { runHookCompatPreflight } from "./runtime.js";

const RESERVED_OPTION_KEYS = new Set([
  "toolName",
  "input",
  "cwd",
  "ctx",
  "runtime",
  "registrations",
  "execute",
  "executor",
]);

function normalizeGuardedOptions(toolName, options) {
  if (!options || typeof options !== "object" || Array.isArray(options)) {
    throw new TypeError(`${toolName} requires an options object.`);
  }
  return options;
}

function resolveGuardedInput(options) {
  if (options.input !== undefined) {
    return options.input;
  }

  const derivedInput = {};
  for (const [key, value] of Object.entries(options)) {
    if (RESERVED_OPTION_KEYS.has(key)) {
      continue;
    }
    derivedInput[key] = value;
  }
  return derivedInput;
}

function resolveExecutor(toolName, options) {
  const execute = options.execute ?? options.executor;
  if (typeof execute !== "function") {
    throw new TypeError(`${toolName} requires an execute callback.`);
  }
  return execute;
}

function normalizeGuardedRequest(toolName, options) {
  return {
    toolName,
    input: resolveGuardedInput(options),
    cwd: normalizeSpawnCwd(options.cwd ?? options.ctx?.cwd),
    ctx: options.ctx,
    runtime: options.runtime,
    registrations: options.registrations,
  };
}

export class HookCompatGuardBlockedError extends Error {
  constructor(message, request, preflight) {
    super(message);
    this.name = "HookCompatGuardBlockedError";
    this.toolName = request.toolName;
    this.input = request.input;
    this.cwd = request.cwd;
    this.preflight = preflight;
  }
}

async function runGuardedExecution(toolName, options) {
  const normalizedOptions = normalizeGuardedOptions(toolName, options);
  const execute = resolveExecutor(toolName, normalizedOptions);
  const request = normalizeGuardedRequest(toolName, normalizedOptions);

  const preflight = await runHookCompatPreflight(request);
  if (preflight?.block) {
    throw new HookCompatGuardBlockedError(preflight.reason ?? `Blocked ${toolName} execution.`, request, preflight);
  }

  return await execute(request);
}

export async function guardedRead(options) {
  return await runGuardedExecution("read", options);
}

export async function guardedGrep(options) {
  return await runGuardedExecution("grep", options);
}

export async function guardedGlob(options) {
  return await runGuardedExecution("glob", options);
}

export async function guardedBash(options) {
  return await runGuardedExecution("bash", options);
}

export async function guardedWrite(options) {
  return await runGuardedExecution("write", options);
}

export async function guardedEdit(options) {
  return await runGuardedExecution("edit", options);
}

export async function guardedNotebookEdit(options) {
  return await runGuardedExecution("NotebookEdit", options);
}
