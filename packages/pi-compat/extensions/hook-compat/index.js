import { clearHookCompatRuntimeState, markHookCompatRuntimeInstalled } from "./registry.js";
import { runHookCompatToolCall } from "./runtime.js";

export default function hookCompatExtension(pi) {
  if (!markHookCompatRuntimeInstalled(pi)) {
    return;
  }

  pi.on("tool_call", async (event, ctx) => {
    return await runHookCompatToolCall(event, ctx, { runtime: pi });
  });

  pi.on("session_shutdown", async () => {
    clearHookCompatRuntimeState(pi);
  });
}

export { registerHookCompatPackage, listRegisteredHookCompatPackages } from "./registry.js";
