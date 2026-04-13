import type { ExtensionContext } from "@mariozechner/pi-coding-agent";
import { formatBraveAuthStatus, getBraveAuthStatus } from "./auth.js";
import { BRAVE_MONTHLY_LIMIT, getBackendAttemptOrder } from "./types.js";
import type { RuntimeState } from "./types.js";

export function formatStatusReport(runtime: RuntimeState): string {
  const remaining = Math.max(0, BRAVE_MONTHLY_LIMIT - runtime.braveUsage.requests_used_this_month);
  const lastBackend = runtime.stats.last_successful_backend ?? "none";
  const snapshot = runtime.lockState.pre_lock_active_tools?.length
    ? runtime.lockState.pre_lock_active_tools.join(", ")
    : "(none)";
  const backendOrder = getBackendAttemptOrder(runtime.defaultBackend).join(" -> ");

  return [
    "web-search status",
    `- lock mode: ${runtime.lockState.locked ? "on" : "off"}`,
    `- web_search calls this session: ${runtime.stats.tool_calls_total}`,
    `- session cache hits: ${runtime.stats.cache_hits_total}`,
    `- configured default backend: ${runtime.defaultBackend}`,
    `- backend attempt order: ${backendOrder}`,
    `- last successful backend: ${lastBackend}`,
    `- backend attempts: brave-search=${runtime.stats.backend_attempts["brave-search"]}, codex-search=${runtime.stats.backend_attempts["codex-search"]}, claude-search=${runtime.stats.backend_attempts["claude-search"]}`,
    `- fallback errors: brave-search=${runtime.stats.fallback_errors["brave-search"]}, codex-search=${runtime.stats.fallback_errors["codex-search"]}, claude-search=${runtime.stats.fallback_errors["claude-search"]}`,
    `- Brave usage this month: ${runtime.braveUsage.requests_used_this_month}/${BRAVE_MONTHLY_LIMIT}`,
    `- Brave remaining this month: ${remaining}`,
    `- pre-lock active tools: ${snapshot}`,
    "",
    formatBraveAuthStatus(runtime.authStorage),
  ].join("\n");
}

export function updateStatusBar(ctx: ExtensionContext | undefined, runtime: RuntimeState): void {
  if (!ctx) {
    return;
  }

  const remaining = Math.max(0, BRAVE_MONTHLY_LIMIT - runtime.braveUsage.requests_used_this_month);
  const backend = runtime.stats.last_successful_backend ?? "none";
  const authSource = getBraveAuthStatus(runtime.authStorage).activeSource;
  const prefix = runtime.lockState.locked ? "🔒" : "🌐";
  ctx.ui.setStatus(
    "web-search",
    `${prefix} web-search default ${runtime.defaultBackend} | last ${backend} | auth ${authSource} | cache ${runtime.stats.cache_hits_total} | Brave ${remaining} left`,
  );
}
