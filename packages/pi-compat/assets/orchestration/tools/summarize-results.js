import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

import { RESULT_STATUSES, normalizeWorkerResult } from "./write-result.js";

const SUMMARY_FORMATS = ["text", "json"];

const SUMMARIZE_RESULTS_USAGE = `Usage: node summarize-results.js \
  --result <path> [--result <path> ...] \
  [--format <text|json>] \
  [--fail-on-missing] \
  [--fail-on-status <warn|fail>]`;

function requireNonEmptyString(value, fieldName) {
  if (typeof value !== "string") {
    throw new TypeError(`Expected ${fieldName} to be a string.`);
  }

  const normalized = value.trim();
  if (normalized.length === 0) {
    throw new TypeError(`Expected ${fieldName} to be a non-empty string.`);
  }

  return normalized;
}

function normalizeSummaryOptions(options = {}) {
  const format = options.format ?? "text";
  if (!SUMMARY_FORMATS.includes(format)) {
    throw new RangeError(
      `Summary format must be one of: ${SUMMARY_FORMATS.join(", ")}. Received: ${format}`,
    );
  }

  const failOnStatus = [...new Set(options.failOnStatus ?? [])].map((status) => requireNonEmptyString(status, "failOnStatus"));
  for (const status of failOnStatus) {
    if (!RESULT_STATUSES.includes(status)) {
      throw new RangeError(
        `--fail-on-status must use one of: ${RESULT_STATUSES.join(", ")}. Received: ${status}`,
      );
    }
  }

  return {
    format,
    failOnMissing: Boolean(options.failOnMissing),
    failOnStatus,
  };
}

export async function readWorkerResult(resultPath) {
  const normalizedResultPath = requireNonEmptyString(resultPath, "resultPath");
  const absoluteResultPath = resolve(normalizedResultPath);

  try {
    const raw = await readFile(absoluteResultPath, "utf8");
    const parsed = JSON.parse(raw);
    const normalized = normalizeWorkerResult(parsed);

    return {
      missing: false,
      result: normalized,
      result_path: normalizedResultPath,
    };
  } catch (error) {
    if (error?.code === "ENOENT") {
      return {
        missing: true,
        result: null,
        result_path: normalizedResultPath,
      };
    }

    throw new Error(`Failed to read worker result ${normalizedResultPath}: ${error.message}`);
  }
}

export async function summarizeWorkerResults(resultPaths, options = {}) {
  if (!Array.isArray(resultPaths) || resultPaths.length === 0) {
    throw new TypeError("summarizeWorkerResults requires at least one result path.");
  }

  const normalizedPaths = resultPaths.map((resultPath) => requireNonEmptyString(resultPath, "resultPath"));
  const normalizedOptions = normalizeSummaryOptions(options);
  const entries = [];
  const totals = {
    expected: normalizedPaths.length,
    present: 0,
    missing: 0,
    success: 0,
    warn: 0,
    fail: 0,
  };

  for (const [index, resultPath] of normalizedPaths.entries()) {
    const loaded = await readWorkerResult(resultPath);

    if (loaded.missing) {
      totals.missing += 1;
      entries.push({
        index: index + 1,
        missing: true,
        report_path: null,
        result_path: loaded.result_path,
        status: "missing",
        summary: "Result file not found.",
        target: null,
        worker_id: null,
      });
      continue;
    }

    totals.present += 1;
    totals[loaded.result.status] += 1;
    entries.push({
      index: index + 1,
      missing: false,
      report_path: loaded.result.report_path,
      result_path: loaded.result_path,
      status: loaded.result.status,
      summary: loaded.result.summary,
      target: loaded.result.target,
      worker_id: loaded.result.worker_id,
    });
  }

  const shouldFail =
    (normalizedOptions.failOnMissing && totals.missing > 0)
    || entries.some((entry) => !entry.missing && normalizedOptions.failOnStatus.includes(entry.status));

  return {
    entries,
    fail_on_missing: normalizedOptions.failOnMissing,
    fail_on_status: normalizedOptions.failOnStatus,
    should_fail: shouldFail,
    totals,
  };
}

export function formatSummary(summary, options = {}) {
  const normalizedOptions = normalizeSummaryOptions(options);

  if (normalizedOptions.format === "json") {
    return `${JSON.stringify(summary, null, 2)}\n`;
  }

  const lines = [
    `Worker results: expected=${summary.totals.expected} present=${summary.totals.present} success=${summary.totals.success} warn=${summary.totals.warn} fail=${summary.totals.fail} missing=${summary.totals.missing}`,
  ];

  for (const entry of summary.entries) {
    const prefix = `${String(entry.index).padStart(2, "0")}. [${entry.status}]`;
    if (entry.missing) {
      lines.push(`${prefix} result=${entry.result_path} summary=${entry.summary}`);
      continue;
    }

    lines.push(
      `${prefix} worker=${entry.worker_id} target=${entry.target} report=${entry.report_path} result=${entry.result_path} summary=${entry.summary}`,
    );
  }

  lines.push(`should_fail=${summary.should_fail}`);
  return `${lines.join("\n")}\n`;
}

export function parseSummarizeResultsCliArgs(argv) {
  const { values } = parseArgs({
    args: argv,
    allowPositionals: false,
    options: {
      "fail-on-missing": {
        type: "boolean",
      },
      "fail-on-status": {
        multiple: true,
        type: "string",
      },
      format: {
        type: "string",
      },
      help: {
        type: "boolean",
      },
      result: {
        multiple: true,
        type: "string",
      },
    },
    strict: true,
  });

  if (values.help) {
    return {
      help: true,
    };
  }

  if (!Array.isArray(values.result) || values.result.length === 0) {
    throw new TypeError(`Missing required arguments: --result\n${SUMMARIZE_RESULTS_USAGE}`);
  }

  const normalizedOptions = normalizeSummaryOptions({
    failOnMissing: values["fail-on-missing"],
    failOnStatus: values["fail-on-status"],
    format: values.format,
  });

  return {
    help: false,
    options: normalizedOptions,
    resultPaths: values.result,
  };
}

export async function main(argv = process.argv.slice(2), io = {}) {
  const stdout = io.stdout ?? process.stdout;
  const stderr = io.stderr ?? process.stderr;

  try {
    const parsed = parseSummarizeResultsCliArgs(argv);

    if (parsed.help) {
      stdout.write(`${SUMMARIZE_RESULTS_USAGE}\n`);
      return 0;
    }

    const summary = await summarizeWorkerResults(parsed.resultPaths, parsed.options);
    stdout.write(formatSummary(summary, parsed.options));
    return summary.should_fail ? 1 : 0;
  } catch (error) {
    stderr.write(`${error.message}\n`);
    return 1;
  }
}

function isDirectExecution() {
  return process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
}

if (isDirectExecution()) {
  process.exitCode = await main();
}

export { SUMMARIZE_RESULTS_USAGE, SUMMARY_FORMATS };
