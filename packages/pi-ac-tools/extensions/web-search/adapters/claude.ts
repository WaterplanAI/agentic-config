import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { AdapterUnavailableError, BackendExecutionError, ParseError, formatErrorMessage } from "../errors.js";
import { normalizeResultShape, parseJsonObjectFromText, stripAnsi, truncateText } from "../normalize.js";
import { buildDelegatePrompt } from "../prompt-builders.js";
import type { AppliedWebSearchRequest, NormalizedSearchResult } from "../types.js";

const CLAUDE_TIMEOUT_MS = 120_000;

export async function runClaudeAdapter(
  pi: ExtensionAPI,
  request: AppliedWebSearchRequest,
  signal: AbortSignal | undefined,
): Promise<NormalizedSearchResult> {
  const prompt = buildDelegatePrompt(request, "claude-search");

  try {
    const result = await pi.exec(
      "npx",
      [
        "@anthropic-ai/claude-code",
        "--model",
        "sonnet",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "WebSearch WebFetch",
        "-p",
        prompt,
      ],
      { signal, timeout: CLAUDE_TIMEOUT_MS },
    );

    if (result.killed) {
      throw new BackendExecutionError("claude-search timed out or was terminated.");
    }

    if (result.code !== 0) {
      const summary = summarizeFailure(result.stderr, result.stdout);
      if (looksUnavailable(summary)) {
        throw new AdapterUnavailableError(summary);
      }
      throw new BackendExecutionError(`claude-search exited with code ${result.code}: ${summary}`);
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
    throw new BackendExecutionError(`claude-search failed: ${message}`);
  }
}

function summarizeFailure(stderr: string, stdout: string): string {
  const merged = [stderr, stdout]
    .map((part) => stripAnsi(part || "").trim())
    .find((part) => part.length > 0);

  return truncateText(merged || "claude-search failed.", 240);
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
    normalized.includes("permission denied") ||
    normalized.includes("could not determine executable to run") ||
    normalized.includes("no such file")
  );
}
