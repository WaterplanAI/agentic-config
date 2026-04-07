export const PI_TO_CLAUDE_TOOL_NAME_MAP = Object.freeze({
  read: "Read",
  grep: "Grep",
  find: "Glob",
  write: "Write",
  edit: "Edit",
  bash: "Bash",
  NotebookEdit: "NotebookEdit",
});

function cloneInput(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return {};
  }
  return { ...input };
}

function remapPathToFilePath(input) {
  const mapped = cloneInput(input);
  if (typeof mapped.path === "string" && mapped.file_path === undefined) {
    mapped.file_path = mapped.path;
  }
  delete mapped.path;
  return mapped;
}

function mapReadInput(input) {
  return remapPathToFilePath(input);
}

function mapWriteInput(input) {
  return remapPathToFilePath(input);
}

function mapEditInput(input) {
  return remapPathToFilePath(input);
}

function mapFindInput(input) {
  const mapped = cloneInput(input);
  return {
    ...mapped,
    pattern: mapped.pattern,
    path: mapped.path,
  };
}

function mapGrepInput(input) {
  const mapped = cloneInput(input);
  return {
    ...mapped,
    pattern: mapped.pattern,
    path: mapped.path,
    glob: mapped.glob,
  };
}

function mapBashInput(input) {
  const mapped = cloneInput(input);
  return {
    ...mapped,
    command: mapped.command,
  };
}

function mapNotebookEditInput(input) {
  const mapped = cloneInput(input);
  if (typeof mapped.path === "string" && mapped.notebook_path === undefined) {
    mapped.notebook_path = mapped.path;
  }
  if (typeof mapped.file_path === "string" && mapped.notebook_path === undefined) {
    mapped.notebook_path = mapped.file_path;
  }
  delete mapped.path;
  delete mapped.file_path;
  return mapped;
}

const INPUT_MAPPERS = Object.freeze({
  read: mapReadInput,
  grep: mapGrepInput,
  find: mapFindInput,
  write: mapWriteInput,
  edit: mapEditInput,
  bash: mapBashInput,
  NotebookEdit: mapNotebookEditInput,
});

export function toClaudeToolName(piToolName) {
  return PI_TO_CLAUDE_TOOL_NAME_MAP[piToolName] ?? piToolName;
}

export function mapPiToolCallToClaudePayload(toolCallOrToolName, maybeInput) {
  const toolName =
    typeof toolCallOrToolName === "string" ? toolCallOrToolName : String(toolCallOrToolName?.toolName ?? "");
  const input = typeof toolCallOrToolName === "string" ? maybeInput : toolCallOrToolName?.input;

  const mapper = INPUT_MAPPERS[toolName] ?? cloneInput;

  return {
    tool_name: toClaudeToolName(toolName),
    tool_input: mapper(input),
  };
}
