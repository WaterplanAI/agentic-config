import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { AdapterUnavailableError, BackendExecutionError, ParseError, formatErrorMessage } from "../errors.js";
import { normalizeResultShape, parseJsonObjectFromText, stripAnsi, truncateText } from "../normalize.js";
import { buildDelegatePrompt } from "../prompt-builders.js";
import type { AppliedWebSearchRequest, NormalizedSearchResult } from "../types.js";

const CODEX_TIMEOUT_MS = 120_000;

export async function runCodexAdapter(
  pi: ExtensionAPI,
  request: AppliedWebSearchRequest,
  signal: AbortSignal | undefined,
): Promise<NormalizedSearchResult> {
  const prompt = buildDelegatePrompt(request, "codex-search");

  try {
    const result = await pi.exec(
      "codex",
      [
        "--model",
        "gpt-5.3-codex",
        "-c",
        'model_reasoning_effort="medium"',
        "--skip-git-repo-check",
        "exec",
        prompt,
      ],
      { signal, timeout: CODEX_TIMEOUT_MS },
    );

    if (result.killed) {
      throw new BackendExecutionError("codex-search timed out or was terminated.");
    }

    if (result.code !== 0) {
      const summary = summarizeFailure(result.stderr, result.stdout);
      if (looksUnavailable(summary)) {
        throw new AdapterUnavailableError(summary);
      }
      throw new BackendExecutionError(`codex-search exited with code ${result.code}: ${summary}`);
    }

    const parsed = parseJsonObjectFromText(result.stdout || result.stderr || "");
    return normalizeResultShape(parsed, request);
  } catch (error) {
    if (error instanceof AdapterUnavailableError || error instanceof BackendExecutionError || error instanceof ParseError) {
      throw error;
    }

    const message = formatErrorMessage(error);
    if (looksUnavailable(message)) {
      throw new AdapterUnavailableError(message);
    }
    throw new BackendExecutionError(`codex-search failed: ${message}`);
  }
}

function summarizeFailure(stderr: string, stdout: string): string {
  const merged = [stderr, stdout]
    .map((part) => stripAnsi(part || "").trim())
    .find((part) => part.length > 0);

  return truncateText(merged || "codex-search failed.", 240);
}

function looksUnavailable(text: string): boolean {
  const normalized = text.toLowerCase();
  return (
    normalized.includes("command not found") ||
    normalized.includes("not installed") ||
    normalized.includes("enoent") ||
    normalized.includes("login") ||
    normalized.includes("authenticate") ||
    normalized.includes("api key") ||
    normalized.includes("not configured") ||
    normalized.includes("no such file")
  );
}
