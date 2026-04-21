import { join } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import { getAgentDir } from "@mariozechner/pi-coding-agent";
import {
  BRAVE_AUTH_PATH,
  BRAVE_AUTH_PROVIDER,
  BRAVE_ENV_VAR,
  clearBraveApiKey,
  createAuthStorage,
  formatBraveAuthStatus,
  runInteractiveBraveSetup,
} from "./auth.js";
import { loadBraveUsageState } from "./adapters/brave.js";
import { disableLockMode, enableLockMode, restoreLockStateFromBranch, shouldBlockNetworkCommand } from "./lock-mode.js";
import { loadDefaultBackend, saveDefaultBackend } from "./preferences.js";
import { updateStatusBar, formatStatusReport } from "./status.js";
import { registerWebSearchTool } from "./tool.js";
import { BACKEND_NAMES, DEFAULT_BACKEND_NAME, createEmptyStats, currentMonthKey } from "./types.js";
import type { BackendName, RuntimeState } from "./types.js";

export default function webSearchExtension(pi: ExtensionAPI): void {
  const runtime: RuntimeState = {
    cache: new Map(),
    inFlight: new Map(),
    lockState: { locked: false },
    stats: createEmptyStats(),
    authStorage: createAuthStorage(),
    braveSetupPromptShown: false,
    braveUsage: { month: currentMonthKey(), requests_used_this_month: 0 },
    braveLane: Promise.resolve(),
    braveLastStartedAt: 0,
    braveUsagePath: join(getAgentDir(), "web-search", "usage.json"),
    defaultBackend: DEFAULT_BACKEND_NAME,
    backendPreferencePath: join(getAgentDir(), "web-search", "preferences.json"),
  };

  registerWebSearchTool(pi, runtime);

  pi.on("tool_call", async (event) => {
    if (runtime.lockState.locked && event.toolName === "bash") {
      return {
        block: true,
        reason: "web-search lock mode is on; use the web_search tool instead.",
      };
    }
  });

  pi.on("user_bash", (event) => {
    if (!runtime.lockState.locked) {
      return;
    }

    if (!shouldBlockNetworkCommand(event.command)) {
      return;
    }

    return {
      result: {
        output: "web-search lock mode is on; use the web_search tool instead.",
        exitCode: 1,
        cancelled: false,
        truncated: false,
      },
    };
  });

  pi.on("session_start", async (_event, ctx) => {
    await resetSessionState(ctx);
  });

  pi.on("session_switch", async (_event, ctx) => {
    await resetSessionState(ctx);
  });

  pi.on("session_fork", async (_event, ctx) => {
    await resetSessionState(ctx);
  });

  pi.on("session_tree", async (_event, ctx) => {
    restoreLockStateFromBranch(pi, ctx, runtime);
    updateStatusBar(ctx, runtime);
  });

  pi.registerCommand("web-search-status", {
    description: "Show web-search backend, cache, quota, and lock status",
    handler: async (_args, ctx) => {
      runtime.authStorage.reload();
      runtime.defaultBackend = await loadDefaultBackend(runtime.backendPreferencePath);
      runtime.braveUsage = await loadBraveUsageState(runtime.braveUsagePath);
      updateStatusBar(ctx, runtime);
      ctx.ui.notify(formatStatusReport(runtime), "info");
    },
  });

  pi.registerCommand("web-search-backend", {
    description: "Inspect or change the default backend: /web-search-backend status|brave-search|codex-search|claude-search",
    handler: async (args, ctx) => {
      const action = (args || "status").trim().toLowerCase();
      runtime.defaultBackend = await loadDefaultBackend(runtime.backendPreferencePath);

      if (action === "" || action === "status") {
        updateStatusBar(ctx, runtime);
        ctx.ui.notify(formatBackendPreferenceStatus(runtime), "info");
        return;
      }

      if (!isBackendName(action)) {
        ctx.ui.notify("Usage: /web-search-backend status|brave-search|codex-search|claude-search", "error");
        return;
      }

      await ctx.waitForIdle();
      runtime.defaultBackend = action;
      await saveDefaultBackend(runtime.backendPreferencePath, runtime.defaultBackend);
      runtime.cache.clear();
      runtime.inFlight.clear();
      updateStatusBar(ctx, runtime);
      ctx.ui.notify(`${formatBackendPreferenceStatus(runtime)}\n- session cache cleared`, "info");
    },
  });

  pi.registerCommand("web-search-lock", {
    description: "Toggle web-search lock mode: /web-search-lock on|off|status",
    handler: async (args, ctx) => {
      const action = (args || "status").trim().toLowerCase();

      if (action === "" || action === "status") {
        runtime.authStorage.reload();
        ctx.ui.notify(formatStatusReport(runtime), "info");
        return;
      }

      if (action !== "on" && action !== "off") {
        ctx.ui.notify("Usage: /web-search-lock on|off|status", "error");
        return;
      }

      await ctx.waitForIdle();

      const message = action === "on" ? enableLockMode(pi, runtime) : disableLockMode(pi, runtime);
      updateStatusBar(ctx, runtime);
      ctx.ui.notify(message, "info");
    },
  });

  pi.registerCommand("web-search-setup", {
    description: "Guide first-time Brave Search API key setup",
    handler: async (_args, ctx) => {
      runtime.authStorage.reload();

      if (!ctx.hasUI) {
        ctx.ui.notify(
          `No interactive UI is available. Set ${BRAVE_ENV_VAR} before starting pi, or store the key in ${BRAVE_AUTH_PATH} under ${BRAVE_AUTH_PROVIDER}.`,
          "info",
        );
        return;
      }

      await ctx.waitForIdle();
      const message = await runInteractiveBraveSetup(runtime.authStorage, ctx, runtime);
      updateStatusBar(ctx, runtime);
      ctx.ui.notify(message, "info");
    },
  });

  pi.registerCommand("web-search-auth", {
    description: "Inspect or clear Brave Search auth: /web-search-auth status|clear",
    handler: async (args, ctx) => {
      runtime.authStorage.reload();
      const action = (args || "status").trim().toLowerCase();

      if (action === "" || action === "status") {
        ctx.ui.notify(formatBraveAuthStatus(runtime.authStorage), "info");
        return;
      }

      if (action !== "clear") {
        ctx.ui.notify("Usage: /web-search-auth status|clear", "error");
        return;
      }

      await ctx.waitForIdle();
      clearBraveApiKey(runtime.authStorage);
      runtime.braveSetupPromptShown = false;
      updateStatusBar(ctx, runtime);
      ctx.ui.notify(`Cleared saved Brave Search API key from ${BRAVE_AUTH_PATH}. Environment variables are unchanged.`, "info");
    },
  });

  async function resetSessionState(ctx: ExtensionContext) {
    runtime.cache.clear();
    runtime.inFlight.clear();
    runtime.stats = createEmptyStats();
    runtime.defaultBackend = await loadDefaultBackend(runtime.backendPreferencePath);
    runtime.braveUsage = await loadBraveUsageState(runtime.braveUsagePath);
    runtime.lockState = { locked: false };
    runtime.braveSetupPromptShown = false;
    runtime.authStorage.reload();
    restoreLockStateFromBranch(pi, ctx, runtime);
    updateStatusBar(ctx, runtime);
  }
}

function isBackendName(value: string): value is BackendName {
  return BACKEND_NAMES.includes(value as BackendName);
}

function formatBackendPreferenceStatus(runtime: RuntimeState): string {
  return [
    "web-search backend",
    `- default backend: ${runtime.defaultBackend}`,
    `- fallback order: ${[runtime.defaultBackend, ...BACKEND_NAMES.filter((backend) => backend !== runtime.defaultBackend)].join(" -> ")}`,
  ].join("\n");
}
