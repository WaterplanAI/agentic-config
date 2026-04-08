import { clearHookCompatRuntimeState, markHookCompatRuntimeInstalled } from "./registry.js";
import { runHookCompatPreflight, runHookCompatToolCall } from "./runtime.js";

function createBlockedSyntheticBashResult(reason) {
  const outputReason = typeof reason === "string" && reason.trim() !== "" ? reason.trim() : "Blocked by hook-compat.";
  return {
    result: {
      output: `${outputReason}\n`,
      exitCode: 126,
      cancelled: false,
      truncated: false,
    },
  };
}

export default function hookCompatExtension(pi) {
  if (!markHookCompatRuntimeInstalled(pi)) {
    return;
  }

  pi.on("tool_call", async (event, ctx) => {
    return await runHookCompatToolCall(event, ctx, { runtime: pi });
  });

  pi.on("user_bash", async (event, ctx) => {
    const preflight = await runHookCompatPreflight({
      toolName: "bash",
      input: { command: event.command },
      cwd: event.cwd,
      ctx,
      runtime: pi,
    });

    if (preflight?.block) {
      return createBlockedSyntheticBashResult(preflight.reason);
    }

    return undefined;
  });

  pi.on("session_shutdown", async () => {
    clearHookCompatRuntimeState(pi);
  });
}

export { registerHookCompatPackage, listRegisteredHookCompatPackages } from "./registry.js";
export { runHookCompatPreflight, runHookCompatToolCall } from "./runtime.js";
export {
  HookCompatGuardBlockedError,
  guardedBash,
  guardedEdit,
  guardedGlob,
  guardedGrep,
  guardedNotebookEdit,
  guardedRead,
  guardedWrite,
} from "./guarded-execution.js";
