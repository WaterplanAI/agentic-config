import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

import askUserExtension from "../index.js";
import { listPiCompatInstalledExtensions, resetPiCompatInstallStateForTests } from "../../_shared/install-guard.js";

test("extension registers AskUserQuestion only once per runtime", () => {
  const tools = [];
  const runtime = {
    registerTool(tool) {
      tools.push(tool);
    },
  };

  askUserExtension(runtime);
  askUserExtension(runtime);

  assert.equal(tools.length, 1);
  assert.equal(tools[0].name, "AskUserQuestion");
  assert.deepEqual(listPiCompatInstalledExtensions(runtime), ["ask-user"]);

  resetPiCompatInstallStateForTests(runtime);
});

test("package.json exposes the ask-user extension entrypoint", () => {
  const packageRoot = fileURLToPath(new URL("../../..", import.meta.url));
  const importProbe = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      'const mod = await import("@agentic-config/pi-compat/extensions/ask-user"); console.log(typeof mod.default);',
    ],
    {
      cwd: packageRoot,
      encoding: "utf8",
    },
  );

  assert.equal(importProbe.status, 0, importProbe.stderr);
  assert.equal(importProbe.stdout.trim(), "function");
});
