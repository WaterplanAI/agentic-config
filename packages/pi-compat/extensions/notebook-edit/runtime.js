import { randomUUID } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const notebookMutationQueue = new Map();

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizeOptionalString(value) {
  if (value === undefined || value === null) {
    return undefined;
  }

  if (typeof value !== "string") {
    return String(value);
  }

  const normalized = value.trim();
  return normalized === "" ? undefined : normalized;
}

function normalizeRequiredString(value, fieldName) {
  const normalized = normalizeOptionalString(value);
  if (!normalized) {
    throw new TypeError(`NotebookEdit requires a non-empty ${fieldName}.`);
  }
  return normalized;
}

function normalizeInteger(value, fieldName) {
  if (!Number.isInteger(value)) {
    throw new TypeError(`NotebookEdit expected ${fieldName} to be an integer.`);
  }
  return value;
}

function toNotebookSource(newSource) {
  if (newSource === "") {
    return [];
  }

  const normalized = newSource.replace(/\r\n/g, "\n");
  const segments = normalized.split("\n");
  return segments.map((segment, index) => (index < segments.length - 1 ? `${segment}\n` : segment));
}

function fromNotebookSource(source) {
  if (Array.isArray(source)) {
    return source.join("");
  }

  if (typeof source === "string") {
    return source;
  }

  return "";
}

function createNotebookCell(cellType, newSource) {
  const baseCell = {
    cell_type: cellType,
    id: randomUUID(),
    metadata: {},
    source: toNotebookSource(newSource),
  };

  if (cellType === "code") {
    return {
      ...baseCell,
      execution_count: null,
      outputs: [],
    };
  }

  return baseCell;
}

function resolveNotebookPath(ctx, notebookPath) {
  return resolve(ctx?.cwd ?? process.cwd(), notebookPath);
}

function resolveTargetCellIndex(notebook, args) {
  if (args.cell_id) {
    const cellIndex = notebook.cells.findIndex((cell) => normalizeOptionalString(cell?.id) === args.cell_id);
    if (cellIndex === -1) {
      throw new RangeError(`NotebookEdit could not find cell_id ${args.cell_id}.`);
    }
    return cellIndex;
  }

  if (args.cell_index !== undefined) {
    if (args.cell_index < 0) {
      throw new RangeError("NotebookEdit cell_index must be zero or greater.");
    }

    if (args.cell_index === notebook.cells.length && args.create_if_missing) {
      return args.cell_index;
    }

    if (args.cell_index >= notebook.cells.length) {
      throw new RangeError(`NotebookEdit cell_index ${args.cell_index} is outside the notebook cell range.`);
    }

    return args.cell_index;
  }

  if (notebook.cells.length === 1) {
    return 0;
  }

  throw new TypeError("NotebookEdit requires cell_index or cell_id when the notebook contains multiple cells.");
}

function validateNotebook(notebook, notebookPath) {
  if (!isObject(notebook) || !Array.isArray(notebook.cells)) {
    throw new TypeError(`NotebookEdit expected ${notebookPath} to contain a Jupyter notebook with a cells array.`);
  }
}

export function normalizeNotebookEditArguments(args) {
  if (!isObject(args)) {
    throw new TypeError("NotebookEdit requires an object of arguments.");
  }

  const cellIndex = args.cell_index === undefined || args.cell_index === null
    ? undefined
    : normalizeInteger(args.cell_index, "cell_index");
  const cellType = normalizeOptionalString(args.cell_type) ?? "code";
  if (!["code", "markdown"].includes(cellType)) {
    throw new TypeError("NotebookEdit cell_type must be either code or markdown.");
  }

  if (args.new_source === undefined || args.new_source === null) {
    throw new TypeError("NotebookEdit requires a non-empty new_source field.");
  }

  return {
    notebook_path: normalizeRequiredString(args.notebook_path ?? args.path ?? args.file_path, "notebook_path"),
    cell_index: cellIndex,
    cell_id: normalizeOptionalString(args.cell_id),
    new_source: typeof args.new_source === "string" ? args.new_source : String(args.new_source),
    create_if_missing: Boolean(args.create_if_missing ?? false),
    cell_type: cellType,
  };
}

export async function applyNotebookEdit(notebookPath, args) {
  const notebookRaw = await readFile(notebookPath, "utf8");
  const notebook = JSON.parse(notebookRaw);
  validateNotebook(notebook, notebookPath);

  const targetIndex = resolveTargetCellIndex(notebook, args);
  let previousSource = "";
  let created = false;
  let targetCell;

  if (targetIndex === notebook.cells.length) {
    targetCell = createNotebookCell(args.cell_type, args.new_source);
    notebook.cells.push(targetCell);
    created = true;
  } else {
    targetCell = notebook.cells[targetIndex];
    if (!isObject(targetCell)) {
      throw new TypeError(`NotebookEdit expected cell ${targetIndex} in ${notebookPath} to be an object.`);
    }
    previousSource = fromNotebookSource(targetCell.source);
    targetCell.source = toNotebookSource(args.new_source);
  }

  await writeFile(notebookPath, `${JSON.stringify(notebook, null, 2)}\n`, "utf8");

  return {
    notebookPath,
    cellIndex: targetIndex,
    cellId: normalizeOptionalString(targetCell.id),
    created,
    previousSource,
    nextSource: args.new_source,
  };
}

async function enqueueNotebookMutation(notebookPath, mutation) {
  const previous = notebookMutationQueue.get(notebookPath) ?? Promise.resolve();
  const next = previous.catch(() => undefined).then(mutation);
  notebookMutationQueue.set(notebookPath, next);

  try {
    return await next;
  } finally {
    if (notebookMutationQueue.get(notebookPath) === next) {
      notebookMutationQueue.delete(notebookPath);
    }
  }
}

export async function executeNotebookEdit(args, ctx) {
  const normalized = normalizeNotebookEditArguments(args);
  const notebookPath = resolveNotebookPath(ctx, normalized.notebook_path);
  const mutation = await enqueueNotebookMutation(notebookPath, () => applyNotebookEdit(notebookPath, normalized));

  const summary = mutation.created
    ? `NotebookEdit appended a new ${normalized.cell_type} cell at index ${mutation.cellIndex} in ${normalized.notebook_path}.`
    : `NotebookEdit updated cell ${mutation.cellIndex} in ${normalized.notebook_path}.`;

  return {
    content: [{ type: "text", text: summary }],
    details: {
      notebookPath: normalized.notebook_path,
      absolutePath: mutation.notebookPath,
      cellIndex: mutation.cellIndex,
      cellId: mutation.cellId,
      created: mutation.created,
      previousSource: mutation.previousSource,
      nextSource: mutation.nextSource,
    },
  };
}
