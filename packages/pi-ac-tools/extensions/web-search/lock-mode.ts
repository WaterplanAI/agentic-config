import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import type { LockState, RuntimeState } from "./types.js";

const LOCK_ENTRY_TYPE = "web-search-lock";
const LOCKED_TOOL_SET = ["read", "ls", "find", "grep", "edit", "write", "web_search"];

const NETWORK_COMMAND_PATTERNS = [
  /(^|\s)curl(\s|$)/i,
  /(^|\s)wget(\s|$)/i,
  /(^|\s)http(\s|$)/i,
  /(^|\s)xh(\s|$)/i,
  /(^|\s)nc(\s|$)/i,
  /(^|\s)ncat(\s|$)/i,
  /(^|\s)socat(\s|$)/i,
  /(^|\s)codex(\s|$)/i,
  /@anthropic-ai\/claude-code/i,
  /\/dev\/tcp/i,
  /python3?\s+-c/i,
  /node\s+-e/i,
  /ruby\s+-e/i,
  /perl\s+-e/i,
  /(^|\s)git\s+(clone|fetch|pull)(\s|$)/i,
  /(^|\s)pip\s+install(\s|$)/i,
];

export function shouldBlockNetworkCommand(command: string): boolean {
  return NETWORK_COMMAND_PATTERNS.some((pattern) => pattern.test(command));
}

export function restoreLockStateFromBranch(
  pi: ExtensionAPI,
  ctx: ExtensionContext,
  runtime: RuntimeState,
): void {
  const restored = readLatestLockState(ctx);

  if (!restored) {
    if (runtime.lockState.locked && runtime.lockState.pre_lock_active_tools?.length) {
      restoreTools(pi, runtime.lockState.pre_lock_active_tools);
    }
    runtime.lockState = { locked: false, pre_lock_active_tools: runtime.lockState.pre_lock_active_tools };
    return;
  }

  runtime.lockState = restored;
  if (restored.locked) {
    applyLockedTools(pi);
  } else if (restored.pre_lock_active_tools && restored.pre_lock_active_tools.length > 0) {
    restoreTools(pi, restored.pre_lock_active_tools);
  }
}

export function enableLockMode(
  pi: ExtensionAPI,
  runtime: RuntimeState,
): string {
  if (runtime.lockState.locked) {
    return "Lock mode is already on.";
  }

  const snapshot = pi.getActiveTools();
  runtime.lockState = {
    locked: true,
    pre_lock_active_tools: snapshot,
  };

  applyLockedTools(pi);
  persistLockState(pi, runtime.lockState);
  return `Lock mode enabled. Active tools: ${filterAvailableTools(pi, LOCKED_TOOL_SET).join(", ")}`;
}

export function disableLockMode(
  pi: ExtensionAPI,
  runtime: RuntimeState,
): string {
  const snapshot = runtime.lockState.pre_lock_active_tools;

  if (!runtime.lockState.locked) {
    if (snapshot && snapshot.length > 0) {
      const restored = restoreTools(pi, snapshot);
      persistLockState(pi, { locked: false, pre_lock_active_tools: snapshot });
      return `Lock mode was already off. Restored saved tools: ${restored.join(", ")}`;
    }
    return "Lock mode is already off.";
  }

  runtime.lockState = {
    locked: false,
    pre_lock_active_tools: snapshot,
  };

  if (snapshot && snapshot.length > 0) {
    const restored = restoreTools(pi, snapshot);
    persistLockState(pi, runtime.lockState);
    return `Lock mode disabled. Restored tools: ${restored.join(", ")}`;
  }

  persistLockState(pi, runtime.lockState);
  return "Lock mode disabled, but no pre-lock tool snapshot was available. Current tools were left unchanged.";
}

function applyLockedTools(pi: ExtensionAPI): void {
  pi.setActiveTools(filterAvailableTools(pi, LOCKED_TOOL_SET));
}

function restoreTools(pi: ExtensionAPI, requestedTools: string[]): string[] {
  const restored = filterAvailableTools(pi, requestedTools);
  if (restored.length > 0) {
    pi.setActiveTools(restored);
  }
  return restored;
}

function filterAvailableTools(pi: ExtensionAPI, requestedTools: string[]): string[] {
  const all = new Set(pi.getAllTools().map((tool) => tool.name));
  return requestedTools.filter((name, index) => requestedTools.indexOf(name) === index && all.has(name));
}

function persistLockState(pi: ExtensionAPI, state: LockState): void {
  pi.appendEntry(LOCK_ENTRY_TYPE, state);
}

function readLatestLockState(ctx: ExtensionContext): LockState | undefined {
  let lastState: LockState | undefined;
  for (const entry of ctx.sessionManager.getBranch()) {
    if (entry.type !== "custom" || entry.customType !== LOCK_ENTRY_TYPE) {
      continue;
    }

    const data = entry.data as Partial<LockState> | undefined;
    if (!data || typeof data.locked !== "boolean") {
      continue;
    }

    lastState = {
      locked: data.locked,
      pre_lock_active_tools: Array.isArray(data.pre_lock_active_tools)
        ? data.pre_lock_active_tools.filter((item): item is string => typeof item === "string")
        : undefined,
    };
  }
  return lastState;
}
