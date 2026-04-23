import { interpretHookDecision } from "./decision.js";
import {
  buildClaudeCompatEnv,
  normalizeSpawnCwd,
  resolveClaudeSessionId,
  resolveHookScriptPath,
} from "./env.js";
import { matchesClaudeMatcher } from "./matchers.js";
import { mapPiToolCallToClaudePayload } from "./payload.js";
import { listRegisteredHookCompatPackages } from "./registry.js";
import { runHookScript } from "./runner.js";

function formatAdapterFailureReason({ packageRegistration, hookRegistration, scriptPath, error }) {
  const prefix = `Hook adapter failure (${packageRegistration.packageId}:${hookRegistration.id})`;
  const scriptSuffix = scriptPath ? ` while executing ${scriptPath}` : "";
  const errorMessage = error instanceof Error ? error.message : String(error);
  return `${prefix}${scriptSuffix}: ${errorMessage}`;
}

function getRegistrationsFromOptions(options) {
  if (Array.isArray(options?.registrations)) {
    return options.registrations;
  }

  if (options?.runtime) {
    return listRegisteredHookCompatPackages(options.runtime);
  }

  throw new TypeError("Hook compatibility runtime requires either options.runtime or explicit options.registrations.");
}

function normalizeHookCompatContext({ cwd, ctx }) {
  const projectDir = normalizeSpawnCwd(cwd ?? ctx?.cwd);
  if (ctx && typeof ctx === "object") {
    if (ctx.cwd === projectDir) {
      return ctx;
    }

    return Object.assign(Object.create(Object.getPrototypeOf(ctx)), ctx, {
      cwd: projectDir,
      hasUI: Boolean(ctx.hasUI),
    });
  }

  return {
    cwd: projectDir,
    hasUI: false,
  };
}

function normalizePreflightToolName(toolName) {
  if (typeof toolName !== "string" || toolName.trim() === "") {
    throw new TypeError("toolName must be a non-empty string.");
  }
  return toolName;
}

async function executeHookCompatPreflight({ claudePayload, ctx, projectDir, sessionId, registrations, runtime }) {
  for (const packageRegistration of registrations) {
    for (const hookGroup of packageRegistration.hooks) {
      if (!matchesClaudeMatcher(hookGroup.matcher, claudePayload.tool_name)) {
        continue;
      }

      for (const hookRegistration of hookGroup.hooks) {
        const scriptPath = resolveHookScriptPath(packageRegistration.pluginRoot, hookRegistration.scriptPath);

        try {
          const env = buildClaudeCompatEnv({
            pluginRoot: packageRegistration.pluginRoot,
            projectDir,
            sessionId,
            hookEnv: hookRegistration.env,
          });

          const { output } = await runHookScript({
            scriptPath,
            payload: claudePayload,
            env,
            cwd: projectDir,
            timeoutMs: hookRegistration.timeoutMs,
          });

          const decision = await interpretHookDecision({
            output,
            ctx,
            packageRegistration,
            hookRegistration,
            runtime,
            claudePayload,
          });

          if (decision.block) {
            return {
              block: true,
              reason: decision.reason,
            };
          }
        } catch (error) {
          if (hookRegistration.failureMode === "fail-open") {
            continue;
          }

          return {
            block: true,
            reason: formatAdapterFailureReason({
              packageRegistration,
              hookRegistration,
              scriptPath,
              error,
            }),
          };
        }
      }
    }
  }

  return undefined;
}

export async function runHookCompatPreflight({ toolName, input, cwd, ctx, runtime, registrations } = {}) {
  try {
    const effectiveRegistrations = getRegistrationsFromOptions({ runtime, registrations });
    if (effectiveRegistrations.length === 0) {
      return undefined;
    }

    const effectiveCtx = normalizeHookCompatContext({ cwd, ctx });
    const normalizedToolName = normalizePreflightToolName(toolName);
    const claudePayload = mapPiToolCallToClaudePayload(normalizedToolName, input);
    const projectDir = effectiveCtx.cwd;
    const sessionId = resolveClaudeSessionId(effectiveCtx);

    return await executeHookCompatPreflight({
      claudePayload,
      ctx: effectiveCtx,
      projectDir,
      sessionId,
      registrations: effectiveRegistrations,
      runtime,
    });
  } catch (error) {
    return {
      block: true,
      reason: `Hook adapter runtime error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

export async function runHookCompatToolCall(event, ctx, options = {}) {
  return await runHookCompatPreflight({
    toolName: event?.toolName,
    input: event?.input,
    cwd: ctx?.cwd,
    ctx,
    runtime: options.runtime,
    registrations: options.registrations,
  });
}
