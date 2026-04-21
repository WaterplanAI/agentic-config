import { createHash } from "node:crypto";
import { isAbsolute, resolve } from "node:path";

function normalizeEnvValue(value) {
  if (value === undefined || value === null) {
    return undefined;
  }
  return String(value);
}

function buildOpaqueSessionId(value, prefix) {
  const digest = createHash("sha256").update(value).digest("hex");
  return `${prefix}-${digest.slice(0, 24)}`;
}

function normalizeClaudeSessionId(value, prefix = "session") {
  const normalized = normalizeEnvValue(value)?.trim();
  if (!normalized) {
    return undefined;
  }

  if (/^[A-Za-z0-9._-]{1,128}$/.test(normalized)) {
    return normalized;
  }

  return buildOpaqueSessionId(normalized, prefix);
}

export function normalizeSpawnCwd(cwd) {
  if (typeof cwd === "string" && cwd.trim() !== "") {
    return resolve(cwd);
  }
  return process.cwd();
}

export function resolveHookScriptPath(pluginRoot, scriptPath) {
  if (typeof scriptPath !== "string" || scriptPath.trim() === "") {
    throw new TypeError("scriptPath must be a non-empty string.");
  }

  if (isAbsolute(scriptPath)) {
    return scriptPath;
  }

  return resolve(pluginRoot, scriptPath);
}

export function resolveClaudeSessionId(ctx) {
  const sessionManager = ctx?.sessionManager;

  if (sessionManager && typeof sessionManager.getSessionId === "function") {
    const sessionId = normalizeClaudeSessionId(sessionManager.getSessionId(), "session");
    if (sessionId) {
      return sessionId;
    }
  }

  if (sessionManager && typeof sessionManager.getSessionFile === "function") {
    const sessionFile = normalizeEnvValue(sessionManager.getSessionFile())?.trim();
    if (sessionFile) {
      return buildOpaqueSessionId(sessionFile, "session-file");
    }
  }

  return String(process.pid);
}

export function buildClaudeCompatEnv({
  pluginRoot,
  projectDir,
  sessionId,
  hookEnv,
  baseEnv = process.env,
}) {
  const claudePluginRoot = normalizeEnvValue(pluginRoot);
  const claudeProjectDir = normalizeEnvValue(projectDir);
  const claudeSessionId = normalizeClaudeSessionId(sessionId, "session");

  if (!claudePluginRoot || !claudeProjectDir || !claudeSessionId) {
    throw new TypeError(
      "pluginRoot, projectDir, and sessionId are required to build the Claude-compatible hook environment.",
    );
  }

  const mergedEnv = {
    ...baseEnv,
    CLAUDE_PLUGIN_ROOT: claudePluginRoot,
    CLAUDE_PROJECT_DIR: claudeProjectDir,
    CLAUDE_SESSION_ID: claudeSessionId,
  };

  if (hookEnv && typeof hookEnv === "object" && !Array.isArray(hookEnv)) {
    for (const [key, value] of Object.entries(hookEnv)) {
      if (value === undefined || value === null) {
        continue;
      }
      mergedEnv[key] = String(value);
    }
  }

  return mergedEnv;
}
