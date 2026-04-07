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

export default function registerAcSafetyHookCompat(pi) {
  registerHookCompatPackage(pi, {
    packageId: "@agentic-config/pi-ac-safety",
    pluginRoot: ASSET_ROOT,
    askFallback: {
      nonInteractive: "deny",
    },
    hooks: [
      {
        matcher: "Read|Grep|Glob",
        hooks: [
          {
            id: "credential-guardian",
            scriptPath: "scripts/hooks/credential-guardian.py",
            timeoutMs: 5000,
            failureMode: "fail-close",
          },
        ],
      },
      {
        matcher: "Bash",
        hooks: [
          {
            id: "destructive-bash-guardian",
            scriptPath: "scripts/hooks/destructive-bash-guardian.py",
            timeoutMs: 5000,
            failureMode: "fail-close",
          },
          {
            id: "supply-chain-guardian",
            scriptPath: "scripts/hooks/supply-chain-guardian.py",
            timeoutMs: 5000,
            failureMode: "fail-close",
          },
          {
            id: "playwright-guardian",
            scriptPath: "scripts/hooks/playwright-guardian.py",
            timeoutMs: 5000,
            failureMode: "fail-close",
          },
        ],
      },
      {
        matcher: "Write|Edit|NotebookEdit",
        hooks: [
          {
            id: "write-scope-guardian",
            scriptPath: "scripts/hooks/write-scope-guardian.py",
            timeoutMs: 5000,
            failureMode: "fail-close",
          },
        ],
      },
    ],
  });
}
