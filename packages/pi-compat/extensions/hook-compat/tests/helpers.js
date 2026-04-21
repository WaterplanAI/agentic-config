import { spawnSync } from "node:child_process";
import { rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));

export const REPO_ROOT = resolve(TEST_DIR, "../../../../..");

export const PLUGIN_ROOTS = Object.freeze({
  acAudit: resolve(REPO_ROOT, "plugins/ac-audit"),
  acGit: resolve(REPO_ROOT, "plugins/ac-git"),
  acSafety: resolve(REPO_ROOT, "plugins/ac-safety"),
  acTools: resolve(REPO_ROOT, "plugins/ac-tools"),
});

export const UV_CACHE_DIR = resolve(tmpdir(), "agentic-config-pi-compat-uv-cache");

export const UV_IS_AVAILABLE = (() => {
  const probe = spawnSync("uv", ["--version"], { encoding: "utf8" });
  return probe.status === 0;
})();

export function createToolCallEvent(toolName, input) {
  return {
    type: "tool_call",
    toolCallId: `hook-compat-test-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    toolName,
    input,
  };
}

export function createTestContext({ cwd, hasUI, confirmResult = true, sessionId = "hook-compat-test-session" }) {
  const notifications = [];
  const confirmations = [];

  const ui = {
    notify(message, level) {
      notifications.push({ message, level });
    },
    async confirm(title, message) {
      confirmations.push({ title, message });
      if (typeof confirmResult === "function") {
        return await confirmResult({ title, message, confirmations: [...confirmations] });
      }
      return Boolean(confirmResult);
    },
  };

  const ctx = {
    cwd,
    hasUI,
    sessionManager: {
      getSessionId() {
        return sessionId;
      },
    },
    ui,
  };

  return {
    ctx,
    notifications,
    confirmations,
  };
}

export function buildHookEnv(homeDir, extra = {}) {
  return {
    HOME: homeDir,
    UV_CACHE_DIR: process.env.UV_CACHE_DIR ?? UV_CACHE_DIR,
    ...extra,
  };
}

export async function cleanupPath(path) {
  await rm(path, { recursive: true, force: true });
}

export function dateStampForToday() {
  const now = new Date();
  const year = String(now.getFullYear());
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
