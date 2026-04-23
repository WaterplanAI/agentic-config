import { resolveClaudeSessionId } from "./env.js";

const ALLOW_ENTRY_TYPE = "hook-compat-allow";
const STATE_SYMBOL = Symbol.for("@agentic-config/pi-compat/hook-compat-allow-state");
const FALLBACK_RUNTIME_KEY = Object.freeze({ name: "hook-compat-global-fallback" });

function createEmptyState() {
  return {
    storesByRuntime: new WeakMap(),
  };
}

function getGlobalState() {
  const scope = globalThis;
  if (!scope[STATE_SYMBOL]) {
    scope[STATE_SYMBOL] = createEmptyState();
  }
  return scope[STATE_SYMBOL];
}

function resolveRuntimeKey(runtime) {
  if ((!runtime || typeof runtime !== "object") && typeof runtime !== "function") {
    return FALLBACK_RUNTIME_KEY;
  }

  const sharedEvents = runtime.events;
  if ((typeof sharedEvents === "object" && sharedEvents !== null) || typeof sharedEvents === "function") {
    return sharedEvents;
  }

  return runtime;
}

function getRuntimeStore(runtime) {
  const runtimeKey = resolveRuntimeKey(runtime);
  const state = getGlobalState();
  const existing = state.storesByRuntime.get(runtimeKey);
  if (existing) {
    return existing;
  }

  const store = new Map();
  state.storesByRuntime.set(runtimeKey, store);
  return store;
}

function getSessionCacheKey(ctx) {
  const sessionId = resolveClaudeSessionId(ctx);
  const cwd = typeof ctx?.cwd === "string" && ctx.cwd.trim() !== "" ? ctx.cwd : process.cwd();
  return `${cwd}::${sessionId}`;
}

function loadPersistedAllowKeys(ctx) {
  const branch = typeof ctx?.sessionManager?.getBranch === "function" ? ctx.sessionManager.getBranch() : [];
  const allowKeys = new Set();

  for (const entry of branch) {
    if (!entry || entry.type !== "custom" || entry.customType !== ALLOW_ENTRY_TYPE) {
      continue;
    }

    const allowKey = entry.data?.allowKey;
    if (typeof allowKey === "string" && allowKey.trim() !== "") {
      allowKeys.add(allowKey);
    }
  }

  return allowKeys;
}

function getSessionAllowSet(runtime, ctx) {
  const runtimeStore = getRuntimeStore(runtime);
  const sessionCacheKey = getSessionCacheKey(ctx);
  const existing = runtimeStore.get(sessionCacheKey);
  if (existing) {
    return existing;
  }

  const loaded = loadPersistedAllowKeys(ctx);
  runtimeStore.set(sessionCacheKey, loaded);
  return loaded;
}

export function hasSessionAllow(runtime, ctx, allowKey) {
  if (typeof allowKey !== "string" || allowKey.trim() === "") {
    return false;
  }

  return getSessionAllowSet(runtime, ctx).has(allowKey);
}

export function grantSessionAllow(runtime, ctx, allowKey) {
  if (typeof allowKey !== "string" || allowKey.trim() === "") {
    return;
  }

  const allowSet = getSessionAllowSet(runtime, ctx);
  if (allowSet.has(allowKey)) {
    return;
  }

  allowSet.add(allowKey);

  if (runtime && typeof runtime.appendEntry === "function") {
    runtime.appendEntry(ALLOW_ENTRY_TYPE, { allowKey });
  }
}

export function clearHookCompatAllowState(runtime) {
  const runtimeKey = resolveRuntimeKey(runtime);
  const state = getGlobalState();
  state.storesByRuntime.delete(runtimeKey);
}

export function resetHookCompatAllowStateForTests() {
  globalThis[STATE_SYMBOL] = createEmptyState();
}
