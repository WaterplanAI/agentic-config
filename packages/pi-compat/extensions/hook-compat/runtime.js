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

export async function runHookCompatToolCall(event, ctx, options = {}) {
  try {
    const registrations = getRegistrationsFromOptions(options);
    if (registrations.length === 0) {
      return undefined;
    }

    const claudePayload = mapPiToolCallToClaudePayload(event);
    const projectDir = normalizeSpawnCwd(ctx?.cwd);
    const sessionId = resolveClaudeSessionId(ctx);

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
  } catch (error) {
    return {
      block: true,
      reason: `Hook adapter runtime error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}
