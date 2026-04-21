import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { normalizeWorkerResult, writeWorkerResult } from "../tools/write-result.js";

async function createWorkspace(prefix) {
  return await mkdtemp(join(tmpdir(), `${prefix}-`));
}

test("normalizeWorkerResult rejects unsupported statuses", () => {
  assert.throws(
    () =>
      normalizeWorkerResult({
        worker_id: "backend",
        status: "done",
        summary: "ready",
        report_path: "reports/backend.md",
        target: "services/api",
      }),
    /status must be one of/i,
  );
});

test("writeWorkerResult writes deterministic normalized JSON", async () => {
  const workspace = await createWorkspace("pi-compat-write-result");

  try {
    const resultPath = resolve(workspace, "results", "backend.json");
    const written = await writeWorkerResult(resultPath, {
      worker_id: " backend ",
      status: "warn",
      summary: " backend venv created with dependency warning ",
      report_path: "reports/backend.md",
      target: "services/api",
    });

    assert.deepEqual(written, {
      worker_id: "backend",
      status: "warn",
      summary: "backend venv created with dependency warning",
      report_path: "reports/backend.md",
      target: "services/api",
    });

    const fileContent = await readFile(resultPath, "utf8");
    assert.equal(
      fileContent,
      `{
  "worker_id": "backend",
  "status": "warn",
  "summary": "backend venv created with dependency warning",
  "report_path": "reports/backend.md",
  "target": "services/api"
}\n`,
    );
  } finally {
    await rm(workspace, { force: true, recursive: true });
  }
});

test("write-result CLI writes the result file and prints normalized JSON", async () => {
  const workspace = await createWorkspace("pi-compat-write-result-cli");

  try {
    const toolPath = fileURLToPath(new URL("../tools/write-result.js", import.meta.url));
    const resultPath = resolve(workspace, "results", "logic.json");
    const command = spawnSync(
      process.execPath,
      [
        toolPath,
        "--result-path",
        resultPath,
        "--worker-id",
        "logic-review",
        "--status",
        "success",
        "--summary",
        "logic checks passed",
        "--report-path",
        "reports/logic.md",
        "--target",
        "logic-bug-risk",
      ],
      {
        encoding: "utf8",
      },
    );

    assert.equal(command.status, 0, command.stderr);
    assert.deepEqual(JSON.parse(command.stdout), {
      worker_id: "logic-review",
      status: "success",
      summary: "logic checks passed",
      report_path: "reports/logic.md",
      target: "logic-bug-risk",
    });

    const fileContent = await readFile(resultPath, "utf8");
    assert.deepEqual(JSON.parse(fileContent), JSON.parse(command.stdout));
  } finally {
    await rm(workspace, { force: true, recursive: true });
  }
});
