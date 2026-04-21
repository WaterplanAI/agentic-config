import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { formatSummary, summarizeWorkerResults } from "../tools/summarize-results.js";
import { writeWorkerResult } from "../tools/write-result.js";

async function createWorkspace(prefix) {
  return await mkdtemp(join(tmpdir(), `${prefix}-`));
}

async function createResult(workspace, fileName, result) {
  const resultPath = resolve(workspace, "results", fileName);
  await writeWorkerResult(resultPath, result);
  return resultPath;
}

test("summarizeWorkerResults preserves requested order and records missing results", async () => {
  const workspace = await createWorkspace("pi-compat-summarize-order");

  try {
    const backendPath = await createResult(workspace, "01-backend.json", {
      worker_id: "backend",
      status: "success",
      summary: "backend environment ready",
      report_path: "reports/backend.md",
      target: "services/api",
    });
    const frontendPath = await createResult(workspace, "02-frontend.json", {
      worker_id: "frontend",
      status: "warn",
      summary: "frontend installed with optional peer warnings",
      report_path: "reports/frontend.md",
      target: "services/web",
    });
    const missingPath = resolve(workspace, "results", "03-data.json");

    const summary = await summarizeWorkerResults(
      [backendPath, frontendPath, missingPath],
      {
        failOnMissing: false,
        failOnStatus: ["fail"],
      },
    );

    assert.deepEqual(summary.totals, {
      expected: 3,
      present: 2,
      missing: 1,
      success: 1,
      warn: 1,
      fail: 0,
    });
    assert.equal(summary.should_fail, false);
    assert.deepEqual(
      summary.entries.map((entry) => entry.worker_id),
      ["backend", "frontend", null],
    );
    assert.equal(summary.entries[2].status, "missing");

    const formatted = formatSummary(summary, { format: "text" });
    assert.match(formatted, /01\. \[success\] worker=backend/);
    assert.match(formatted, /02\. \[warn\] worker=frontend/);
    assert.match(formatted, /03\. \[missing\] result=.*03-data\.json/);
    assert.match(formatted, /should_fail=false/);
  } finally {
    await rm(workspace, { force: true, recursive: true });
  }
});

test("representative worktree wave tolerates warn results when only fail is fatal", async () => {
  const workspace = await createWorkspace("pi-compat-summarize-worktree");

  try {
    const resultPaths = await Promise.all([
      createResult(workspace, "01-backend.json", {
        worker_id: "backend-env",
        status: "success",
        summary: "backend Python environment configured",
        report_path: "reports/backend.md",
        target: "trees/abc123-feature/services/api",
      }),
      createResult(workspace, "02-frontend.json", {
        worker_id: "frontend-env",
        status: "warn",
        summary: "frontend install completed with peer dependency warnings",
        report_path: "reports/frontend.md",
        target: "trees/abc123-feature/services/web",
      }),
      createResult(workspace, "03-direnv.json", {
        worker_id: "direnv-env",
        status: "success",
        summary: "direnv allow completed",
        report_path: "reports/direnv.md",
        target: "trees/abc123-feature",
      }),
    ]);

    const summary = await summarizeWorkerResults(resultPaths, {
      failOnMissing: true,
      failOnStatus: ["fail"],
    });

    assert.equal(summary.should_fail, false);
    assert.equal(summary.totals.warn, 1);
    assert.deepEqual(
      summary.entries.map((entry) => entry.worker_id),
      ["backend-env", "frontend-env", "direnv-env"],
    );
  } finally {
    await rm(workspace, { force: true, recursive: true });
  }
});

test("representative gh-pr-review wave emits deterministic JSON and exits non-zero on failed workers", async () => {
  const workspace = await createWorkspace("pi-compat-summarize-review");

  try {
    const orderedPaths = await Promise.all([
      createResult(workspace, "01-expected.json", {
        worker_id: "expected-changes",
        status: "success",
        summary: "expected change coverage matched the brief",
        report_path: "reports/01_expected.md",
        target: "expected-changes",
      }),
      createResult(workspace, "02-security.json", {
        worker_id: "security-review",
        status: "success",
        summary: "no security regressions found",
        report_path: "reports/02_security.md",
        target: "security",
      }),
      createResult(workspace, "03-quality.json", {
        worker_id: "code-quality-review",
        status: "warn",
        summary: "lint surfaced one new style issue",
        report_path: "reports/03_code_quality.md",
        target: "code-quality",
      }),
      createResult(workspace, "04-tests.json", {
        worker_id: "test-review",
        status: "fail",
        summary: "new regression test failed on changed code path",
        report_path: "reports/04_tests.md",
        target: "tests",
      }),
      createResult(workspace, "05-logic.json", {
        worker_id: "logic-review",
        status: "success",
        summary: "logic flow matched expected behavior",
        report_path: "reports/05_logic_bugs.md",
        target: "logic-bug-risk",
      }),
    ]);

    const toolPath = fileURLToPath(new URL("../tools/summarize-results.js", import.meta.url));
    const command = spawnSync(
      process.execPath,
      [
        toolPath,
        ...orderedPaths.flatMap((resultPath) => ["--result", resultPath]),
        "--format",
        "json",
        "--fail-on-status",
        "fail",
      ],
      {
        encoding: "utf8",
      },
    );

    assert.equal(command.status, 1, command.stderr);
    const summary = JSON.parse(command.stdout);
    assert.equal(summary.should_fail, true);
    assert.equal(summary.totals.fail, 1);
    assert.equal(summary.totals.warn, 1);
    assert.deepEqual(
      summary.entries.map((entry) => entry.worker_id),
      [
        "expected-changes",
        "security-review",
        "code-quality-review",
        "test-review",
        "logic-review",
      ],
    );
  } finally {
    await rm(workspace, { force: true, recursive: true });
  }
});
