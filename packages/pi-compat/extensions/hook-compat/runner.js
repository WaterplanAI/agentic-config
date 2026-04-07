import { spawn } from "node:child_process";

export class HookExecutionError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "HookExecutionError";
    this.code = code;
    this.details = details;
  }
}

function parseHookStdout(stdout) {
  const trimmed = stdout.trim();

  if (!trimmed) {
    return null;
  }

  try {
    return JSON.parse(trimmed);
  } catch {
    const lines = trimmed.split(/\r?\n/).map((line) => line.trim()).filter((line) => line !== "");
    if (lines.length > 1) {
      const lastLine = lines[lines.length - 1];
      try {
        return JSON.parse(lastLine);
      } catch {
        // Fall through to detailed error.
      }
    }

    throw new HookExecutionError(
      "INVALID_JSON",
      "Hook script emitted invalid JSON on stdout.",
      {
        stdout,
      },
    );
  }
}

function normalizeTimeoutMs(timeoutMs) {
  if (typeof timeoutMs !== "number" || !Number.isFinite(timeoutMs)) {
    return 5000;
  }
  return Math.max(1, Math.trunc(timeoutMs));
}

export async function runHookScript({ scriptPath, payload, env, cwd, timeoutMs }) {
  if (typeof scriptPath !== "string" || scriptPath.trim() === "") {
    throw new TypeError("scriptPath must be a non-empty string.");
  }

  const effectiveTimeoutMs = normalizeTimeoutMs(timeoutMs);
  const serializedPayload = JSON.stringify(payload ?? {});

  return await new Promise((resolve, reject) => {
    const child = spawn("uv", ["run", "--no-project", "--script", scriptPath], {
      cwd,
      env,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let timedOut = false;

    const timeoutHandle = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");

      const killHandle = setTimeout(() => {
        child.kill("SIGKILL");
      }, 250);
      killHandle.unref();
    }, effectiveTimeoutMs);

    child.on("error", (error) => {
      clearTimeout(timeoutHandle);
      reject(
        new HookExecutionError("SPAWN_ERROR", `Failed to spawn hook script: ${error.message}`, {
          scriptPath,
          cause: error,
        }),
      );
    });

    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
    });

    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });

    child.on("close", (exitCode, signal) => {
      clearTimeout(timeoutHandle);

      if (timedOut) {
        reject(
          new HookExecutionError(
            "TIMEOUT",
            `Hook script timed out after ${effectiveTimeoutMs}ms.`,
            {
              scriptPath,
              timeoutMs: effectiveTimeoutMs,
              stdout,
              stderr,
            },
          ),
        );
        return;
      }

      if (exitCode !== 0) {
        reject(
          new HookExecutionError(
            "NON_ZERO_EXIT",
            `Hook script exited with code ${exitCode}${signal ? ` (signal: ${signal})` : ""}.`,
            {
              scriptPath,
              exitCode,
              signal,
              stdout,
              stderr,
            },
          ),
        );
        return;
      }

      try {
        const output = parseHookStdout(stdout);
        resolve({
          output,
          stdout,
          stderr,
          exitCode,
        });
      } catch (error) {
        if (error instanceof HookExecutionError) {
          reject(error);
          return;
        }

        reject(
          new HookExecutionError("UNKNOWN_PARSE_ERROR", "Failed to parse hook output.", {
            scriptPath,
            stdout,
            stderr,
            cause: error,
          }),
        );
      }
    });

    child.stdin.on("error", (error) => {
      clearTimeout(timeoutHandle);
      reject(
        new HookExecutionError("STDIN_WRITE_ERROR", `Failed to write hook payload: ${error.message}`, {
          scriptPath,
          cause: error,
        }),
      );
    });

    child.stdin.write(serializedPayload);
    child.stdin.end();
  });
}
