import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import { getBraveAuthStatus } from "./auth.js";
import { AdapterUnavailableError, formatErrorMessage } from "./errors.js";
import { loadDefaultBackend } from "./preferences.js";
import { buildToolResult, cloneToolResult, formatFallbackChain } from "./response.js";
import { runBraveAdapter } from "./adapters/brave.js";
import { runCodexAdapter } from "./adapters/codex.js";
import { runClaudeAdapter } from "./adapters/claude.js";
import type {
  AppliedWebSearchRequest,
  BackendAttempt,
  BackendName,
  NormalizedSearchResult,
  RuntimeState,
  ToolResultPayload,
} from "./types.js";
import { getBackendAttemptOrder } from "./types.js";
import { createRequestCacheKey } from "./request.js";

export async function executeWebSearch(
  pi: ExtensionAPI,
  request: AppliedWebSearchRequest,
  signal: AbortSignal | undefined,
  runtime: RuntimeState,
  ctx: ExtensionContext,
): Promise<ToolResultPayload> {
  runtime.stats.tool_calls_total += 1;
  runtime.defaultBackend = await loadDefaultBackend(runtime.backendPreferencePath);

  const cacheKey = createRequestCacheKey(request, runtime.defaultBackend);
  const braveAuthSource = getBraveAuthStatus(runtime.authStorage).activeSource;
  const cached = runtime.cache.get(cacheKey);
  if (cached) {
    runtime.stats.cache_hits_total += 1;
    return cloneToolResult(cached, true, braveAuthSource);
  }

  const inFlight = runtime.inFlight.get(cacheKey);
  if (inFlight) {
    return cloneToolResult(await inFlight, false, braveAuthSource);
  }

  const execution = runFreshSearch(pi, request, signal, runtime, ctx)
    .then((result) => {
      runtime.cache.set(cacheKey, cloneToolResult(result, false, getBraveAuthStatus(runtime.authStorage).activeSource));
      return result;
    })
    .finally(() => {
      runtime.inFlight.delete(cacheKey);
    });

  runtime.inFlight.set(cacheKey, execution);
  return cloneToolResult(await execution, false, getBraveAuthStatus(runtime.authStorage).activeSource);
}

async function runFreshSearch(
  pi: ExtensionAPI,
  request: AppliedWebSearchRequest,
  signal: AbortSignal | undefined,
  runtime: RuntimeState,
  ctx: ExtensionContext,
): Promise<ToolResultPayload> {
  const fallbackChain: BackendAttempt[] = [];

  for (const backend of getBackendAttemptOrder(runtime.defaultBackend)) {
    runtime.stats.backend_attempts[backend] += 1;

    try {
      const normalized = await executeBackend(pi, backend, request, signal, runtime, ctx);
      fallbackChain.push({ backend, status: "success" });
      runtime.stats.last_successful_backend = backend;
      return buildToolResult(
        request,
        normalized,
        backend,
        fallbackChain,
        false,
        getBraveAuthStatus(runtime.authStorage).activeSource,
      );
    } catch (error) {
      if (error instanceof AdapterUnavailableError) {
        fallbackChain.push({ backend, status: "skipped", reason: error.message });
        continue;
      }

      const message = formatErrorMessage(error);
      runtime.stats.fallback_errors[backend] += 1;
      fallbackChain.push({ backend, status: "error", reason: message });
    }
  }

  throw new Error(`web_search failed for ${JSON.stringify(request.q)}. Attempt chain: ${formatFallbackChain(fallbackChain)}`);
}

async function executeBackend(
  pi: ExtensionAPI,
  backend: BackendName,
  request: AppliedWebSearchRequest,
  signal: AbortSignal | undefined,
  runtime: RuntimeState,
  ctx: ExtensionContext,
): Promise<NormalizedSearchResult> {
  switch (backend) {
    case "brave-search":
      return runBraveAdapter(pi, request, signal, runtime, ctx);
    case "codex-search":
      return runCodexAdapter(pi, request, signal);
    case "claude-search":
      return runClaudeAdapter(pi, request, signal);
    default:
      throw new Error(`Unsupported backend: ${backend}`);
  }
}
