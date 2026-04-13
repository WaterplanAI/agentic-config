import { join } from "node:path";
import { AuthStorage, getAgentDir } from "@mariozechner/pi-coding-agent";
import type { ExtensionContext } from "@mariozechner/pi-coding-agent";
import type { RuntimeState } from "./types.js";

export const BRAVE_AUTH_PROVIDER = "web-search-brave";
export const BRAVE_ENV_VAR = "BRAVE_SEARCH_API_KEY";
export const BRAVE_AUTH_PATH = join(getAgentDir(), "auth.json");

export interface BraveAuthStatus {
  envConfigured: boolean;
  authConfigured: boolean;
  activeSource: "env" | "auth.json" | "none";
}

export function createAuthStorage(): AuthStorage {
  return AuthStorage.create();
}

export function getBraveAuthStatus(authStorage: AuthStorage): BraveAuthStatus {
  const envConfigured = Boolean(normalizeSecret(process.env[BRAVE_ENV_VAR]));
  const authConfigured = authStorage.has(BRAVE_AUTH_PROVIDER);

  return {
    envConfigured,
    authConfigured,
    activeSource: envConfigured ? "env" : authConfigured ? "auth.json" : "none",
  };
}

export async function resolveBraveApiKey(
  authStorage: AuthStorage,
  ctx: ExtensionContext | undefined,
  runtime: RuntimeState,
): Promise<string | undefined> {
  authStorage.reload();

  const envKey = normalizeSecret(process.env[BRAVE_ENV_VAR]);
  if (envKey) {
    return envKey;
  }

  const savedKey = normalizeSecret(await authStorage.getApiKey(BRAVE_AUTH_PROVIDER, { includeFallback: false }));
  if (savedKey) {
    return savedKey;
  }

  await maybePromptForBraveSetup(authStorage, ctx, runtime);

  const envKeyAfterPrompt = normalizeSecret(process.env[BRAVE_ENV_VAR]);
  if (envKeyAfterPrompt) {
    return envKeyAfterPrompt;
  }

  return normalizeSecret(await authStorage.getApiKey(BRAVE_AUTH_PROVIDER, { includeFallback: false }));
}

export function setBraveApiKey(authStorage: AuthStorage, apiKey: string): void {
  const normalized = normalizeSecret(apiKey);
  if (!normalized) {
    throw new Error("Brave Search API key must not be empty.");
  }

  authStorage.set(BRAVE_AUTH_PROVIDER, {
    type: "api_key",
    key: normalized,
  });
}

export function clearBraveApiKey(authStorage: AuthStorage): void {
  authStorage.remove(BRAVE_AUTH_PROVIDER);
}

export function formatBraveAuthStatus(authStorage: AuthStorage): string {
  const status = getBraveAuthStatus(authStorage);

  return [
    "web-search auth",
    `- ${BRAVE_ENV_VAR}: ${status.envConfigured ? "configured" : "not configured"}`,
    `- ${BRAVE_AUTH_PATH} (${BRAVE_AUTH_PROVIDER}): ${status.authConfigured ? "configured" : "not configured"}`,
    `- active source: ${status.activeSource}`,
  ].join("\n");
}

export function missingBraveKeySetupHint(): string {
  return [
    "Brave Search API key is not configured.",
    `Set ${BRAVE_ENV_VAR} or store the key in ${BRAVE_AUTH_PATH} under ${BRAVE_AUTH_PROVIDER}.`,
    "Use /web-search-setup for guided setup.",
  ].join(" ");
}

export async function runInteractiveBraveSetup(
  authStorage: AuthStorage,
  ctx: ExtensionContext,
  runtime: RuntimeState,
): Promise<string> {
  const status = getBraveAuthStatus(authStorage);
  const saveLabel = status.authConfigured ? "Replace saved key in Pi auth store" : "Save key in Pi auth store";
  const choice = await ctx.ui.select("Configure Brave Search", [
    saveLabel,
    "Use environment variable instead",
    "Not now",
  ]);

  runtime.braveSetupPromptShown = true;

  if (!choice || choice === "Not now") {
    return "Brave Search setup skipped. web_search will use fallback backends when possible.";
  }

  if (choice === "Use environment variable instead") {
    return [
      `Set ${BRAVE_ENV_VAR} before starting pi, then restart pi.`,
      `Example: export ${BRAVE_ENV_VAR}=...`,
      `Or save the key in ${BRAVE_AUTH_PATH} via /web-search-setup.`,
    ].join("\n");
  }

  const prompt = status.authConfigured
    ? `Enter the new Brave Search API key (visible locally while typing) to save in ${BRAVE_AUTH_PATH}`
    : `Enter the Brave Search API key (visible locally while typing) to save in ${BRAVE_AUTH_PATH}`;
  const value = await ctx.ui.input(prompt, "Paste API key here");
  const normalized = normalizeSecret(value);

  if (!normalized) {
    return "Brave Search setup canceled. No key was saved.";
  }

  setBraveApiKey(authStorage, normalized);
  return `Saved Brave Search API key in ${BRAVE_AUTH_PATH}. This file uses Pi's auth store and is kept outside the project.`;
}

async function maybePromptForBraveSetup(
  authStorage: AuthStorage,
  ctx: ExtensionContext | undefined,
  runtime: RuntimeState,
): Promise<void> {
  if (!ctx?.hasUI || runtime.braveSetupPromptShown) {
    return;
  }

  const status = getBraveAuthStatus(authStorage);
  if (status.activeSource !== "none") {
    return;
  }

  const message = await runInteractiveBraveSetup(authStorage, ctx, runtime);
  ctx.ui.notify(message, "info");
}

function normalizeSecret(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }

  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
}
