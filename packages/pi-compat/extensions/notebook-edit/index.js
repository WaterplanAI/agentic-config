import { markPiCompatExtensionInstalled } from "../_shared/install-guard.js";
import { executeNotebookEdit, normalizeNotebookEditArguments } from "./runtime.js";

const NOTEBOOK_EDIT_PARAMETERS = {
  type: "object",
  properties: {
    notebook_path: {
      type: "string",
      description: "Path to the .ipynb file to edit.",
    },
    cell_index: {
      type: "integer",
      description: "Zero-based cell index to replace. Required unless cell_id is provided or the notebook has exactly one cell.",
    },
    cell_id: {
      type: "string",
      description: "Optional stable cell id to target instead of cell_index.",
    },
    new_source: {
      type: "string",
      description: "Replacement source text for the targeted cell.",
    },
    create_if_missing: {
      type: "boolean",
      description: "When true, allow appending a new cell when cell_index equals the current cell count.",
    },
    cell_type: {
      type: "string",
      enum: ["code", "markdown"],
      description: "Cell type to use when appending a new cell. Defaults to code.",
    },
  },
  required: ["notebook_path", "new_source"],
  additionalProperties: false,
};

export default function notebookEditExtension(pi) {
  if (!markPiCompatExtensionInstalled(pi, "notebook-edit")) {
    return;
  }

  pi.registerTool({
    name: "NotebookEdit",
    label: "Notebook Edit",
    description: "Replace the source of a targeted Jupyter notebook cell or append a new cell when explicitly requested.",
    promptSnippet: "Edit one cell in a Jupyter notebook without rewriting the entire .ipynb file manually.",
    promptGuidelines: [
      "Always target a specific cell_index or cell_id when the notebook has multiple cells.",
      "Use create_if_missing only when you intentionally want to append a new cell.",
      "Treat this as a source-edit tool only; it does not execute notebooks or manage outputs.",
    ],
    parameters: NOTEBOOK_EDIT_PARAMETERS,
    prepareArguments: normalizeNotebookEditArguments,
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      return await executeNotebookEdit(params, ctx);
    },
  });
}
