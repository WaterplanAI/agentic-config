export class HookDecisionError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "HookDecisionError";
    this.details = details;
  }
}

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

async function resolveAskDecision({ reason, ctx, packageRegistration, hookRegistration }) {
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

export async function interpretHookDecision({ output, ctx, packageRegistration, hookRegistration }) {
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
    });
  }

  throw new HookDecisionError(`Unsupported permissionDecision value: ${rawDecision}.`, {
    output,
    packageId: packageRegistration.packageId,
    hookId: hookRegistration.id,
  });
}
