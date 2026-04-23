import { createHash } from "node:crypto";

import { clearHookCompatAllowState, grantSessionAllow, hasSessionAllow } from "./allow-state.js";
import { buildClaudeCompatEnv, normalizeSpawnCwd, resolveClaudeSessionId, resolveHookScriptPath } from "./env.js";
import { runHookScript } from "./runner.js";

export class HookDecisionError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "HookDecisionError";
    this.details = details;
  }
}

const ASK_ALLOW_ONCE = "Allow once";
const ASK_ALLOW_SESSION = "Allow for rest of this session";
const ASK_ALLOW_PROJECT = "Always allow in this project";
const ASK_ALLOW_USER = "Always allow from now on";
const ASK_DENY = "Deny";

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasHookSpecificOutput(output) {
  return isObject(output) && Object.prototype.hasOwnProperty.call(output, "hookSpecificOutput");
}

function resolveHookSpecificOutput(output) {
  if (!isObject(output)) {
    return null;
  }

  if (isObject(output.hookSpecificOutput)) {
    return output.hookSpecificOutput;
  }

  return null;
}

function resolveSystemMessage(output) {
  if (!isObject(output)) {
    return undefined;
  }

  if (typeof output.systemMessage === "string" && output.systemMessage.trim() !== "") {
    return output.systemMessage;
  }

  return undefined;
}

function notifySystemMessage(ctx, systemMessage) {
  if (!systemMessage || !ctx?.hasUI || typeof ctx?.ui?.notify !== "function") {
    return;
  }

  try {
    ctx.ui.notify(systemMessage, "info");
  } catch {
    // Best-effort user messaging by contract.
  }
}

function resolvePermissionDecisionMetadata(hookSpecificOutput) {
  if (!isObject(hookSpecificOutput)) {
    return null;
  }

  const metadata = hookSpecificOutput.permissionDecisionMetadata;
  return isObject(metadata) ? metadata : null;
}

function buildDefaultAllowKey({ packageRegistration, hookRegistration, claudePayload, reason }) {
  const digest = createHash("sha256")
    .update(
      JSON.stringify({
        packageId: packageRegistration?.packageId ?? "",
        hookId: hookRegistration?.id ?? "",
        toolName: claudePayload?.tool_name ?? "",
        toolInput: claudePayload?.tool_input ?? {},
        reason: reason ?? "",
      }),
    )
    .digest("hex");

  return `hook-compat:${packageRegistration?.packageId ?? "package"}:${hookRegistration?.id ?? "hook"}:${digest.slice(0, 24)}`;
}

function resolveAllowKey({ metadata, packageRegistration, hookRegistration, claudePayload, reason }) {
  if (typeof metadata?.allowKey === "string" && metadata.allowKey.trim() !== "") {
    return metadata.allowKey;
  }

  return buildDefaultAllowKey({
    packageRegistration,
    hookRegistration,
    claudePayload,
    reason,
  });
}

function resolvePersistenceAction(metadata, scope) {
  if (!isObject(metadata)) {
    return null;
  }

  const fieldName = scope === "project" ? "projectPersistence" : "userPersistence";
  const action = metadata[fieldName];
  return isObject(action) ? action : null;
}

function buildSelectOptions({ allowProject, allowUser }) {
  const options = [ASK_ALLOW_ONCE, ASK_ALLOW_SESSION];
  if (allowProject) {
    options.push(ASK_ALLOW_PROJECT);
  }
  if (allowUser) {
    options.push(ASK_ALLOW_USER);
  }
  options.push(ASK_DENY);
  return options;
}

function formatAskPrompt(reason) {
  const trimmed = typeof reason === "string" ? reason.trim() : "";
  if (!trimmed) {
    return "Hook confirmation";
  }
  return `Hook confirmation\n\n${trimmed}`;
}

async function executePersistenceAction({ action, ctx, packageRegistration, hookRegistration }) {
  if (!isObject(action)) {
    throw new HookDecisionError("Persistence action must be an object.", {
      packageId: packageRegistration?.packageId,
      hookId: hookRegistration?.id,
      action,
    });
  }

  const scriptPath = resolveHookScriptPath(packageRegistration.pluginRoot, action.scriptPath);
  const projectDir = normalizeSpawnCwd(ctx?.cwd);
  const sessionId = resolveClaudeSessionId(ctx);
  const env = buildClaudeCompatEnv({
    pluginRoot: packageRegistration.pluginRoot,
    projectDir,
    sessionId,
    hookEnv: isObject(action.env) ? action.env : undefined,
  });

  const { output } = await runHookScript({
    scriptPath,
    payload: isObject(action.payload) ? action.payload : {},
    env,
    cwd: projectDir,
    timeoutMs:
      typeof action.timeoutMs === "number" && Number.isFinite(action.timeoutMs)
        ? action.timeoutMs
        : hookRegistration?.timeoutMs,
  });

  if (ctx?.hasUI && typeof ctx?.ui?.notify === "function" && typeof output?.message === "string" && output.message.trim()) {
    ctx.ui.notify(output.message, "info");
  }

  return output;
}

async function resolveAskDecision({
  reason,
  ctx,
  packageRegistration,
  hookRegistration,
  runtime,
  claudePayload,
  metadata,
}) {
  const allowKey = resolveAllowKey({
    metadata,
    packageRegistration,
    hookRegistration,
    claudePayload,
    reason,
  });

  if (hasSessionAllow(runtime, ctx, allowKey)) {
    return {
      block: false,
      decision: "allow",
    };
  }

  const projectPersistence = resolvePersistenceAction(metadata, "project");
  const userPersistence = resolvePersistenceAction(metadata, "user");

  if (ctx?.hasUI && typeof ctx?.ui?.select === "function") {
    const choice = await ctx.ui.select(
      formatAskPrompt(reason ?? "Hook requested confirmation."),
      buildSelectOptions({
        allowProject: Boolean(projectPersistence),
        allowUser: Boolean(userPersistence),
      }),
    );

    if (choice === ASK_ALLOW_ONCE) {
      return {
        block: false,
        decision: "allow",
      };
    }

    if (choice === ASK_ALLOW_SESSION) {
      grantSessionAllow(runtime, ctx, allowKey);
      return {
        block: false,
        decision: "allow",
      };
    }

    if (choice === ASK_ALLOW_PROJECT) {
      try {
        await executePersistenceAction({
          action: projectPersistence,
          ctx,
          packageRegistration,
          hookRegistration,
        });
      } catch (error) {
        return {
          block: true,
          decision: "deny",
          reason: `Failed to persist project allow: ${error instanceof Error ? error.message : String(error)}`,
        };
      }

      grantSessionAllow(runtime, ctx, allowKey);
      return {
        block: false,
        decision: "allow",
      };
    }

    if (choice === ASK_ALLOW_USER) {
      try {
        await executePersistenceAction({
          action: userPersistence,
          ctx,
          packageRegistration,
          hookRegistration,
        });
      } catch (error) {
        return {
          block: true,
          decision: "deny",
          reason: `Failed to persist user allow: ${error instanceof Error ? error.message : String(error)}`,
        };
      }

      grantSessionAllow(runtime, ctx, allowKey);
      return {
        block: false,
        decision: "allow",
      };
    }

    return {
      block: true,
      decision: "deny",
      reason: reason ? `Blocked by user: ${reason}` : "Blocked by user.",
    };
  }

  if (ctx?.hasUI && typeof ctx?.ui?.confirm === "function") {
    const approved = await ctx.ui.confirm("Hook confirmation", reason ?? "Hook requested confirmation.");
    if (approved) {
      return {
        block: false,
        decision: "allow",
      };
    }

    return {
      block: true,
      decision: "deny",
      reason: reason ? `Blocked by user: ${reason}` : "Blocked by user.",
    };
  }

  if (packageRegistration?.askFallback?.nonInteractive === "allow") {
    return {
      block: false,
      decision: "allow",
    };
  }

  return {
    block: true,
    decision: "deny",
    reason:
      reason ??
      `Blocked by ${packageRegistration.packageId}:${hookRegistration.id}. Hook requested confirmation but UI is unavailable.`,
  };
}

export async function interpretHookDecision({
  output,
  ctx,
  packageRegistration,
  hookRegistration,
  runtime,
  claudePayload,
}) {
  if (output === null || output === undefined) {
    return {
      block: false,
      decision: "none",
    };
  }

  if (!isObject(output)) {
    throw new HookDecisionError("Hook output must be a JSON object when present.", {
      output,
      packageId: packageRegistration.packageId,
      hookId: hookRegistration.id,
    });
  }

  const systemMessage = resolveSystemMessage(output);
  const hookSpecificOutput = resolveHookSpecificOutput(output);
  if (!hookSpecificOutput) {
    if (hasHookSpecificOutput(output)) {
      throw new HookDecisionError("hookSpecificOutput must be an object when present.", {
        output,
        packageId: packageRegistration.packageId,
        hookId: hookRegistration.id,
      });
    }

    notifySystemMessage(ctx, systemMessage);

    return {
      block: false,
      decision: "none",
    };
  }

  const rawDecision = hookSpecificOutput.permissionDecision;
  if (rawDecision === undefined || rawDecision === null || String(rawDecision).trim() === "") {
    notifySystemMessage(ctx, systemMessage);

    return {
      block: false,
      decision: "none",
    };
  }

  const decision = String(rawDecision).toLowerCase();
  const reason =
    typeof hookSpecificOutput.permissionDecisionReason === "string"
      ? hookSpecificOutput.permissionDecisionReason
      : undefined;
  const metadata = resolvePermissionDecisionMetadata(hookSpecificOutput);

  if (decision === "allow") {
    notifySystemMessage(ctx, systemMessage);

    return {
      block: false,
      decision: "allow",
    };
  }

  if (decision === "deny") {
    notifySystemMessage(ctx, systemMessage);

    return {
      block: true,
      decision: "deny",
      reason: reason ?? `Blocked by ${packageRegistration.packageId}:${hookRegistration.id}.`,
    };
  }

  if (decision === "ask") {
    notifySystemMessage(ctx, systemMessage);

    return await resolveAskDecision({
      reason,
      ctx,
      packageRegistration,
      hookRegistration,
      runtime,
      claudePayload,
      metadata,
    });
  }

  throw new HookDecisionError(`Unsupported permissionDecision value: ${rawDecision}.`, {
    output,
    packageId: packageRegistration.packageId,
    hookId: hookRegistration.id,
  });
}

export { clearHookCompatAllowState };
