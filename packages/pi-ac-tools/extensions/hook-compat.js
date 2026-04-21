import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ASSET_ROOT = resolve(PACKAGE_ROOT, "assets");

const { registerHookCompatPackage } = await loadHookCompatModule();

async function loadHookCompatModule() {
  try {
    return await import("@agentic-config/pi-compat/extensions/hook-compat");
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code !== "ERR_MODULE_NOT_FOUND") {
      throw error;
    }
    return await import(new URL("../../pi-compat/extensions/hook-compat/index.js", import.meta.url).href);
  }
}

export default function registerAcToolsHookCompat(pi) {
  registerHookCompatPackage(pi, {
    packageId: "@agentic-config/pi-ac-tools",
    pluginRoot: ASSET_ROOT,
    askFallback: {
      nonInteractive: "deny",
    },
    hooks: [
      {
        matcher: "Write|Edit|NotebookEdit|Bash",
        hooks: [
          {
            id: "dry-run-guard",
            scriptPath: "scripts/hooks/dry-run-guard.py",
            timeoutMs: 5000,
            failureMode: "fail-open",
          },
        ],
      },
      {
        matcher: "Bash",
        hooks: [
          {
            id: "gsuite-public-asset-guard",
            scriptPath: "scripts/hooks/gsuite-public-asset-guard.py",
            timeoutMs: 5000,
            failureMode: "fail-open",
          },
        ],
      },
    ],
  });
}
