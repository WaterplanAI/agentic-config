import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

export const RESULT_STATUSES = ["success", "warn", "fail"];

const REQUIRED_FIELDS = ["worker_id", "status", "summary", "report_path", "target"];

const WRITE_RESULT_USAGE = `Usage: node write-result.js \
  --result-path <path> \
  --worker-id <id> \
  --status <success|warn|fail> \
  --summary <summary> \
  --report-path <path> \
  --target <target>`;

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

export function normalizeWorkerResult(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new TypeError("Worker result must be an object.");
  }

  const workerId = requireNonEmptyString(input.worker_id, "worker_id");
  const status = requireNonEmptyString(input.status, "status");

  if (!RESULT_STATUSES.includes(status)) {
    throw new RangeError(
      `Worker result status must be one of: ${RESULT_STATUSES.join(", ")}. Received: ${status}`,
    );
  }

  const summary = requireNonEmptyString(input.summary, "summary");
  const reportPath = requireNonEmptyString(input.report_path, "report_path");
  const target = requireNonEmptyString(input.target, "target");

  return {
    worker_id: workerId,
    status,
    summary,
    report_path: reportPath,
    target,
  };
}

export async function writeWorkerResult(resultPath, input) {
  const normalizedResultPath = requireNonEmptyString(resultPath, "resultPath");
  const normalized = normalizeWorkerResult(input);
  const absoluteResultPath = resolve(normalizedResultPath);

  await mkdir(dirname(absoluteResultPath), { recursive: true });
  await writeFile(absoluteResultPath, `${JSON.stringify(normalized, null, 2)}\n`, "utf8");

  return normalized;
}

export function parseWriteResultCliArgs(argv) {
  const { values } = parseArgs({
    args: argv,
    allowPositionals: false,
    options: {
      help: {
        type: "boolean",
      },
      "report-path": {
        type: "string",
      },
      "result-path": {
        type: "string",
      },
      status: {
        type: "string",
      },
      summary: {
        type: "string",
      },
      target: {
        type: "string",
      },
      "worker-id": {
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

  const missing = [
    ["result-path", values["result-path"]],
    ["worker-id", values["worker-id"]],
    ["status", values.status],
    ["summary", values.summary],
    ["report-path", values["report-path"]],
    ["target", values.target],
  ].filter(([, value]) => value === undefined);

  if (missing.length > 0) {
    throw new TypeError(
      `Missing required arguments: ${missing.map(([name]) => `--${name}`).join(", ")}\n${WRITE_RESULT_USAGE}`,
    );
  }

  return {
    help: false,
    resultPath: values["result-path"],
    result: normalizeWorkerResult({
      worker_id: values["worker-id"],
      status: values.status,
      summary: values.summary,
      report_path: values["report-path"],
      target: values.target,
    }),
  };
}

export async function main(argv = process.argv.slice(2), io = {}) {
  const stdout = io.stdout ?? process.stdout;
  const stderr = io.stderr ?? process.stderr;

  try {
    const parsed = parseWriteResultCliArgs(argv);

    if (parsed.help) {
      stdout.write(`${WRITE_RESULT_USAGE}\n`);
      return 0;
    }

    const result = await writeWorkerResult(parsed.resultPath, parsed.result);
    stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return 0;
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

export { REQUIRED_FIELDS, WRITE_RESULT_USAGE };
