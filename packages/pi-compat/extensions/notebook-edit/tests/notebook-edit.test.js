import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";

import { executeNotebookEdit, normalizeNotebookEditArguments } from "../runtime.js";

async function createNotebookWorkspace(prefix) {
  const rootDir = await mkdtemp(join(tmpdir(), `${prefix}-`));
  const notebookPath = resolve(rootDir, "sample.ipynb");
  const notebook = {
    cells: [
      {
        cell_type: "code",
        execution_count: 1,
        metadata: {},
        outputs: [],
        source: ["print(\"before\")\n"],
      },
      {
        cell_type: "markdown",
        metadata: {},
        source: ["# Title\n"],
      },
    ],
    metadata: {},
    nbformat: 4,
    nbformat_minor: 5,
  };

  await writeFile(notebookPath, `${JSON.stringify(notebook, null, 2)}\n`, "utf8");
  return { rootDir, notebookPath };
}

test("normalizes notebook edit arguments and accepts path alias", () => {
  const normalized = normalizeNotebookEditArguments({
    path: "notes.ipynb",
    cell_index: 0,
    new_source: "print(\"hi\")\n",
  });

  assert.equal(normalized.notebook_path, "notes.ipynb");
  assert.equal(normalized.cell_index, 0);
  assert.equal(normalized.cell_type, "code");
});

test("requires new_source instead of silently coercing an empty edit", () => {
  assert.throws(
    () =>
      normalizeNotebookEditArguments({
        notebook_path: "notes.ipynb",
        cell_index: 0,
      }),
    /new_source/i,
  );
});

test("updates an existing notebook cell by index", async () => {
  const workspace = await createNotebookWorkspace("notebook-edit-update");
  const result = await executeNotebookEdit(
    {
      notebook_path: "sample.ipynb",
      cell_index: 1,
      new_source: "# Updated\n",
    },
    {
      cwd: workspace.rootDir,
    },
  );

  assert.match(result.content[0].text, /updated cell 1/i);
  assert.equal(result.details.created, false);

  const updatedNotebook = JSON.parse(await readFile(workspace.notebookPath, "utf8"));
  assert.equal(updatedNotebook.cells[1].source.join(""), "# Updated\n");
});

test("can append a new cell when create_if_missing is enabled", async () => {
  const workspace = await createNotebookWorkspace("notebook-edit-append");
  const result = await executeNotebookEdit(
    {
      notebook_path: "sample.ipynb",
      cell_index: 2,
      create_if_missing: true,
      cell_type: "markdown",
      new_source: "## Added\n",
    },
    {
      cwd: workspace.rootDir,
    },
  );

  assert.match(result.content[0].text, /appended a new markdown cell/i);
  assert.equal(result.details.created, true);

  const updatedNotebook = JSON.parse(await readFile(workspace.notebookPath, "utf8"));
  assert.equal(updatedNotebook.cells.length, 3);
  assert.equal(updatedNotebook.cells[2].cell_type, "markdown");
  assert.equal(updatedNotebook.cells[2].source.join(""), "## Added\n");
  assert.equal(typeof updatedNotebook.cells[2].id, "string");
  assert.notEqual(updatedNotebook.cells[2].id.trim(), "");
});
