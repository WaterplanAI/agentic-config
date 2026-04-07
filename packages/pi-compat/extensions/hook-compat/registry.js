import { resolve } from "node:path";

import { parseClaudeMatcher } from "./matchers.js";

const REGISTRY_SYMBOL = Symbol.for("@agentic-config/pi-compat/hook-compat-registry");
const VALID_FAILURE_MODES = new Set(["fail-open", "fail-close"]);

function createEmptyState() {
  return {
    installedRuntimes: new WeakSet(),
    registrationsByRuntime: new WeakMap(),
  };
}

function getRegistryState() {
  const scope = globalThis;
  if (!scope[REGISTRY_SYMBOL]) {
    scope[REGISTRY_SYMBOL] = createEmptyState();
  }
  return scope[REGISTRY_SYMBOL];
}

function assertRuntime(runtime) {
  if ((!runtime || typeof runtime !== "object") && typeof runtime !== "function") {
    throw new TypeError("runtime must be a non-null object.");
  }
}

function getRuntimeRegistrations(runtime) {
  assertRuntime(runtime);

  const state = getRegistryState();
  const existing = state.registrationsByRuntime.get(runtime);
  if (existing) {
    return existing;
  }

  const registrations = new Map();
  state.registrationsByRuntime.set(runtime, registrations);
  return registrations;
}

function assertNonEmptyString(value, fieldName) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new TypeError(`Expected ${fieldName} to be a non-empty string.`);
  }
}

function normalizeHookRegistration(packageId, hookGroupIndex, hookIndex, hookRegistration) {
  if (!hookRegistration || typeof hookRegistration !== "object") {
    throw new TypeError(`Expected hooks[${hookIndex}] for ${packageId} to be an object.`);
  }

  const scriptPath = hookRegistration.scriptPath;
  assertNonEmptyString(scriptPath, `hooks[${hookIndex}].scriptPath`);

  const timeoutMs =
    typeof hookRegistration.timeoutMs === "number" && Number.isFinite(hookRegistration.timeoutMs)
      ? Math.max(1, Math.trunc(hookRegistration.timeoutMs))
      : 5000;

  const failureMode = hookRegistration.failureMode ?? "fail-close";
  if (!VALID_FAILURE_MODES.has(failureMode)) {
    throw new TypeError(
      `Expected hooks[${hookIndex}].failureMode to be one of: ${Array.from(VALID_FAILURE_MODES).join(", ")}.`,
    );
  }

  const normalizedEnv = {};
  if (hookRegistration.env !== undefined) {
    if (!hookRegistration.env || typeof hookRegistration.env !== "object" || Array.isArray(hookRegistration.env)) {
      throw new TypeError(`Expected hooks[${hookIndex}].env to be an object when provided.`);
    }
    for (const [key, value] of Object.entries(hookRegistration.env)) {
      normalizedEnv[key] = String(value);
    }
  }

  return {
    id: hookRegistration.id ?? `${packageId}:${hookGroupIndex}:${hookIndex}`,
    scriptPath: scriptPath.trim(),
    timeoutMs,
    failureMode,
    env: normalizedEnv,
  };
}

function normalizeHookGroup(packageId, hookGroupIndex, hookGroup) {
  if (!hookGroup || typeof hookGroup !== "object") {
    throw new TypeError(`Expected hooks[${hookGroupIndex}] for ${packageId} to be an object.`);
  }

  const matcher = hookGroup.matcher;
  assertNonEmptyString(matcher, `hooks[${hookGroupIndex}].matcher`);
  parseClaudeMatcher(matcher);

  if (!Array.isArray(hookGroup.hooks) || hookGroup.hooks.length === 0) {
    throw new TypeError(`Expected hooks[${hookGroupIndex}].hooks for ${packageId} to be a non-empty array.`);
  }

  return {
    matcher: matcher.trim(),
    hooks: hookGroup.hooks.map((hookRegistration, hookIndex) =>
      normalizeHookRegistration(packageId, hookGroupIndex, hookIndex, hookRegistration),
    ),
  };
}

function normalizePackageRegistration(packageRegistration) {
  if (!packageRegistration || typeof packageRegistration !== "object") {
    throw new TypeError("Expected package registration to be an object.");
  }

  const { packageId, pluginRoot, hooks, askFallback } = packageRegistration;

  assertNonEmptyString(packageId, "packageId");
  assertNonEmptyString(pluginRoot, "pluginRoot");

  if (!Array.isArray(hooks) || hooks.length === 0) {
    throw new TypeError(`Expected hooks for ${packageId} to be a non-empty array.`);
  }

  const normalizedAskFallback = {
    nonInteractive: askFallback?.nonInteractive === "allow" ? "allow" : "deny",
  };

  return {
    packageId: packageId.trim(),
    pluginRoot: resolve(pluginRoot),
    askFallback: normalizedAskFallback,
    hooks: hooks.map((hookGroup, hookGroupIndex) => normalizeHookGroup(packageId, hookGroupIndex, hookGroup)),
  };
}

function cloneRegistration(registration) {
  return {
    packageId: registration.packageId,
    pluginRoot: registration.pluginRoot,
    askFallback: { ...registration.askFallback },
    hooks: registration.hooks.map((group) => ({
      matcher: group.matcher,
      hooks: group.hooks.map((hook) => ({
        id: hook.id,
        scriptPath: hook.scriptPath,
        timeoutMs: hook.timeoutMs,
        failureMode: hook.failureMode,
        env: { ...hook.env },
      })),
    })),
  };
}

export function registerHookCompatPackage(runtime, packageRegistration) {
  const normalizedRegistration = normalizePackageRegistration(packageRegistration);
  const registrations = getRuntimeRegistrations(runtime);
  const status = registrations.has(normalizedRegistration.packageId) ? "replaced" : "registered";

  registrations.set(normalizedRegistration.packageId, normalizedRegistration);

  return {
    status,
    registration: cloneRegistration(normalizedRegistration),
  };
}

export function listRegisteredHookCompatPackages(runtime) {
  const registrations = getRuntimeRegistrations(runtime);
  return Array.from(registrations.values(), (registration) => cloneRegistration(registration));
}

export function markHookCompatRuntimeInstalled(runtime) {
  assertRuntime(runtime);

  const state = getRegistryState();
  if (state.installedRuntimes.has(runtime)) {
    return false;
  }

  state.installedRuntimes.add(runtime);
  return true;
}

export function clearHookCompatRuntimeState(runtime) {
  assertRuntime(runtime);

  const state = getRegistryState();
  state.installedRuntimes.delete(runtime);
  state.registrationsByRuntime.delete(runtime);
}

export function resetHookCompatRegistryForTests() {
  const scope = globalThis;
  scope[REGISTRY_SYMBOL] = createEmptyState();
}
