import { mkdir, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import { resolveBraveApiKey, missingBraveKeySetupHint } from "../auth.js";
import { AdapterUnavailableError, BackendExecutionError, ParseError, formatErrorMessage } from "../errors.js";
import { normalizeResultShape } from "../normalize.js";
import type { AppliedWebSearchRequest, BraveUsageState, NormalizedSearchResult, RuntimeState } from "../types.js";
import { BRAVE_MONTHLY_LIMIT, currentMonthKey } from "../types.js";

const BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/llm/context";
const BRAVE_TIMEOUT_MS = 30_000;
const BRAVE_CONNECT_TIMEOUT_SECONDS = "5";
const BRAVE_REQUEST_SPACING_MS = 1_000;

export async function loadBraveUsageState(usagePath: string): Promise<BraveUsageState> {
  try {
    const text = await readFile(usagePath, "utf8");
    const parsed = JSON.parse(text) as Partial<BraveUsageState>;
    const month = typeof parsed.month === "string" ? parsed.month : currentMonthKey();
    const requests = Number(parsed.requests_used_this_month ?? 0);
    if (month !== currentMonthKey()) {
      return { month: currentMonthKey(), requests_used_this_month: 0 };
    }
    return {
      month,
      requests_used_this_month: Number.isFinite(requests) && requests >= 0 ? Math.trunc(requests) : 0,
    };
  } catch {
    return { month: currentMonthKey(), requests_used_this_month: 0 };
  }
}

export async function runBraveAdapter(
  pi: ExtensionAPI,
  request: AppliedWebSearchRequest,
  signal: AbortSignal | undefined,
  runtime: RuntimeState,
  ctx: ExtensionContext | undefined,
): Promise<NormalizedSearchResult> {
  const apiKey = await resolveBraveApiKey(runtime.authStorage, ctx, runtime);
  if (!apiKey) {
    throw new AdapterUnavailableError(missingBraveKeySetupHint());
  }

  return withBraveLane(runtime, signal, async () => {
    await ensureCurrentBraveMonth(runtime);
    if (runtime.braveUsage.requests_used_this_month >= BRAVE_MONTHLY_LIMIT) {
      throw new AdapterUnavailableError("Brave monthly quota is exhausted.");
    }

    const tempDir = await mkdtemp(join(tmpdir(), "pi-web-search-brave-"));
    const bodyPath = join(tempDir, "request.json");
    const configPath = join(tempDir, "curl.conf");
    const responsePath = join(tempDir, "response.json");

    let shouldCountRequest = false;

    try {
      await writeFile(bodyPath, JSON.stringify(buildRequestBody(request)), { mode: 0o600 });
      await writeFile(configPath, buildCurlConfig(apiKey, request), { mode: 0o600 });

      shouldCountRequest = true;
      const result = await pi.exec(
        "env",
        [
          "-i",
          ...buildMinimalEnv(),
          "curl",
          "-q",
          "--globoff",
          "--fail-with-body",
          "--proto",
          "=https",
          "--tlsv1.2",
          "--silent",
          "--show-error",
          "--connect-timeout",
          BRAVE_CONNECT_TIMEOUT_SECONDS,
          "--max-time",
          String(Math.ceil(BRAVE_TIMEOUT_MS / 1000)),
          "--request",
          "POST",
          "--config",
          configPath,
          "--data-binary",
          `@${bodyPath}`,
          "--output",
          responsePath,
          "--write-out",
          "%{http_code}",
        ],
        { signal, timeout: BRAVE_TIMEOUT_MS + 5_000 },
      );

      if (result.killed) {
        throw new BackendExecutionError("Brave request timed out or was terminated.");
      }

      const responseText = await safeRead(responsePath);
      const statusCode = Number.parseInt((result.stdout || "").trim(), 10);

      if (result.code !== 0) {
        const stderr = [result.stderr, responseText].filter(Boolean).join("\n").trim();
        if (looksLikeMissingCurl(stderr)) {
          shouldCountRequest = false;
          throw new AdapterUnavailableError("curl is not available for Brave requests.");
        }
        throw new BackendExecutionError(extractBraveError(stderr) || `Brave request failed with exit code ${result.code}.`);
      }

      if (!Number.isFinite(statusCode) || statusCode < 200 || statusCode >= 300) {
        throw new BackendExecutionError(
          extractBraveError(responseText) || `Brave request failed with HTTP status ${Number.isFinite(statusCode) ? statusCode : "unknown"}.`,
        );
      }

      if (!responseText.trim()) {
        throw new ParseError("Brave returned an empty response body.");
      }

      const parsed = JSON.parse(responseText);
      return normalizeResultShape(parsed, request);
    } catch (error) {
      if (error instanceof AdapterUnavailableError || error instanceof BackendExecutionError || error instanceof ParseError) {
        throw error;
      }

      const message = formatErrorMessage(error);
      if (looksLikeMissingCurl(message)) {
        shouldCountRequest = false;
        throw new AdapterUnavailableError("curl is not available for Brave requests.");
      }

      throw new BackendExecutionError(`Brave request failed: ${message}`);
    } finally {
      if (shouldCountRequest) {
        runtime.braveUsage.requests_used_this_month += 1;
        await saveBraveUsageState(runtime.braveUsagePath, runtime.braveUsage);
      }
      await rm(tempDir, { recursive: true, force: true }).catch(() => undefined);
    }
  });
}

async function withBraveLane<T>(
  runtime: RuntimeState,
  signal: AbortSignal | undefined,
  task: () => Promise<T>,
): Promise<T> {
  const previous = runtime.braveLane;
  let release = () => undefined;
  runtime.braveLane = previous.catch(() => undefined).then(
    () =>
      new Promise<void>((resolve) => {
        release = resolve;
      }),
  );

  await previous.catch(() => undefined);

  try {
    const elapsed = Date.now() - runtime.braveLastStartedAt;
    const waitMs = Math.max(0, BRAVE_REQUEST_SPACING_MS - elapsed);
    if (waitMs > 0) {
      await sleep(waitMs, signal);
    }

    runtime.braveLastStartedAt = Date.now();
    return await task();
  } finally {
    release();
  }
}

async function sleep(ms: number, signal: AbortSignal | undefined): Promise<void> {
  if (signal?.aborted) {
    throw new BackendExecutionError("Brave request aborted.");
  }

  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);

    const onAbort = () => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
      reject(new BackendExecutionError("Brave request aborted."));
    };

    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

async function ensureCurrentBraveMonth(runtime: RuntimeState): Promise<void> {
  const month = currentMonthKey();
  if (runtime.braveUsage.month !== month) {
    runtime.braveUsage = { month, requests_used_this_month: 0 };
    await saveBraveUsageState(runtime.braveUsagePath, runtime.braveUsage);
  }
}

async function saveBraveUsageState(usagePath: string, state: BraveUsageState): Promise<void> {
  await mkdir(dirname(usagePath), { recursive: true });
  const tempPath = `${usagePath}.tmp`;
  await writeFile(tempPath, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });
  await rename(tempPath, usagePath);
}

function buildRequestBody(request: AppliedWebSearchRequest): Record<string, unknown> {
  return {
    q: request.q,
    ...(request.country ? { country: request.country } : {}),
    ...(request.search_lang ? { search_lang: request.search_lang } : {}),
    count: request.count,
    ...(request.freshness ? { freshness: request.freshness } : {}),
    maximum_number_of_urls: request.maximum_number_of_urls,
    maximum_number_of_tokens: request.maximum_number_of_tokens,
    maximum_number_of_snippets: request.maximum_number_of_snippets,
    maximum_number_of_tokens_per_url: request.maximum_number_of_tokens_per_url,
    maximum_number_of_snippets_per_url: request.maximum_number_of_snippets_per_url,
    context_threshold_mode: request.context_threshold_mode,
    ...(request.enable_local === undefined ? {} : { enable_local: request.enable_local }),
    ...(request.goggles && request.goggles.length > 0
      ? { goggles: request.goggles.length === 1 ? request.goggles[0] : request.goggles }
      : {}),
  };
}

function buildCurlConfig(apiKey: string, request: AppliedWebSearchRequest): string {
  const lines = [
    `url = ${quote(BRAVE_ENDPOINT)}`,
    `header = ${quote("Accept: application/json")}`,
    `header = ${quote("Content-Type: application/json")}`,
    `header = ${quote(`X-Subscription-Token: ${apiKey}`)}`,
  ];

  if (request.location) {
    const headers = locationHeaders(request.location);
    for (const header of headers) {
      lines.push(`header = ${quote(header)}`);
    }
  }

  return `${lines.join("\n")}\n`;
}

function locationHeaders(location: AppliedWebSearchRequest["location"]): string[] {
  if (!location) {
    return [];
  }

  const headers: string[] = [];
  if (typeof location.lat === "number") headers.push(`X-Loc-Lat: ${location.lat}`);
  if (typeof location.long === "number") headers.push(`X-Loc-Long: ${location.long}`);
  if (location.city) headers.push(`X-Loc-City: ${location.city}`);
  if (location.state) headers.push(`X-Loc-State: ${location.state}`);
  if (location.state_name) headers.push(`X-Loc-State-Name: ${location.state_name}`);
  if (location.country) headers.push(`X-Loc-Country: ${location.country}`);
  if (location.postal_code) headers.push(`X-Loc-Postal-Code: ${location.postal_code}`);
  return headers;
}

function quote(value: string): string {
  return JSON.stringify(value);
}

function buildMinimalEnv(): string[] {
  const env: string[] = [];
  const allow = ["PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR"];
  for (const key of allow) {
    const value = process.env[key];
    if (value && value.length > 0) {
      env.push(`${key}=${value}`);
    }
  }
  if (!env.some((entry) => entry.startsWith("PATH="))) {
    env.push("PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin");
  }
  if (!env.some((entry) => entry.startsWith("HOME=")) && process.env.HOME) {
    env.push(`HOME=${process.env.HOME}`);
  }
  return env;
}

async function safeRead(path: string): Promise<string> {
  try {
    return await readFile(path, "utf8");
  } catch {
    return "";
  }
}

function looksLikeMissingCurl(text: string): boolean {
  const normalized = text.toLowerCase();
  return normalized.includes("curl: not found") || normalized.includes("no such file") || normalized.includes("command not found");
}

function extractBraveError(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }

  try {
    const parsed = JSON.parse(trimmed) as { error?: { message?: string }; message?: string };
    if (parsed?.error?.message) {
      return parsed.error.message;
    }
    if (parsed?.message) {
      return parsed.message;
    }
  } catch {
    // Fall back to text extraction below.
  }

  const firstLine = trimmed.split(/\r?\n/).find((line) => line.trim().length > 0);
  return firstLine ? firstLine.trim() : trimmed;
}
