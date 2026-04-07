import { isAbsolute, resolve } from "node:path";

function normalizeEnvValue(value) {
  if (value === undefined || value === null) {
    return undefined;
  }
  return String(value);
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
    const sessionId = normalizeEnvValue(sessionManager.getSessionId());
    if (sessionId) {
      return sessionId;
    }
  }

  if (sessionManager && typeof sessionManager.getSessionFile === "function") {
    const sessionFile = normalizeEnvValue(sessionManager.getSessionFile());
    if (sessionFile) {
      return sessionFile;
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
  const claudeSessionId = normalizeEnvValue(sessionId);

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
