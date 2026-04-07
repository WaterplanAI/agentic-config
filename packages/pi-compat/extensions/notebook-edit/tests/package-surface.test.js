import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

import notebookEditExtension from "../index.js";
import { listPiCompatInstalledExtensions, resetPiCompatInstallStateForTests } from "../../_shared/install-guard.js";

test("extension registers NotebookEdit only once per runtime", () => {
  const tools = [];
  const runtime = {
    registerTool(tool) {
      tools.push(tool);
    },
  };

  notebookEditExtension(runtime);
  notebookEditExtension(runtime);

  assert.equal(tools.length, 1);
  assert.equal(tools[0].name, "NotebookEdit");
  assert.deepEqual(listPiCompatInstalledExtensions(runtime), ["notebook-edit"]);

  resetPiCompatInstallStateForTests(runtime);
});

test("package.json exposes the notebook-edit extension entrypoint", () => {
  const packageRoot = fileURLToPath(new URL("../../..", import.meta.url));
  const importProbe = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      'const mod = await import("@agentic-config/pi-compat/extensions/notebook-edit"); console.log(typeof mod.default);',
    ],
    {
      cwd: packageRoot,
      encoding: "utf8",
    },
  );

  assert.equal(importProbe.status, 0, importProbe.stderr);
  assert.equal(importProbe.stdout.trim(), "function");
});
