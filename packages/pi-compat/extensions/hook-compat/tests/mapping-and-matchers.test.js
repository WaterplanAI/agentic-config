import assert from "node:assert/strict";
import test from "node:test";

import { matchesClaudeMatcher } from "../matchers.js";
import { mapPiToolCallToClaudePayload } from "../payload.js";

test("maps read payload to Claude Read schema", () => {
  const payload = mapPiToolCallToClaudePayload({
    toolName: "read",
    input: {
      path: "README.md",
      offset: 10,
      limit: 50,
    },
  });

  assert.deepEqual(payload, {
    tool_name: "Read",
    tool_input: {
      file_path: "README.md",
      offset: 10,
      limit: 50,
    },
  });
});

test("maps grep/find/write/edit/bash/NotebookEdit payloads per the locked table", () => {
  assert.deepEqual(
    mapPiToolCallToClaudePayload({
      toolName: "grep",
      input: { pattern: "TODO", path: "src", glob: "*.js" },
    }),
    {
      tool_name: "Grep",
      tool_input: { pattern: "TODO", path: "src", glob: "*.js" },
    },
  );

  assert.deepEqual(
    mapPiToolCallToClaudePayload({
      toolName: "find",
      input: { pattern: "*.md", path: "docs" },
    }),
    {
      tool_name: "Glob",
      tool_input: { pattern: "*.md", path: "docs" },
    },
  );

  assert.deepEqual(
    mapPiToolCallToClaudePayload({
      toolName: "write",
      input: { path: "notes.txt", content: "hello" },
    }),
    {
      tool_name: "Write",
      tool_input: { file_path: "notes.txt", content: "hello" },
    },
  );

  assert.deepEqual(
    mapPiToolCallToClaudePayload({
      toolName: "edit",
      input: { path: "notes.txt", edits: [] },
    }),
    {
      tool_name: "Edit",
      tool_input: { file_path: "notes.txt", edits: [] },
    },
  );

  assert.deepEqual(
    mapPiToolCallToClaudePayload({
      toolName: "bash",
      input: { command: "echo hello", timeout: 30 },
    }),
    {
      tool_name: "Bash",
      tool_input: { command: "echo hello", timeout: 30 },
    },
  );

  assert.deepEqual(
    mapPiToolCallToClaudePayload({
      toolName: "NotebookEdit",
      input: {
        path: "notebooks/demo.ipynb",
        cell_index: 1,
        new_source: "print('hello')\n",
      },
    }),
    {
      tool_name: "NotebookEdit",
      tool_input: {
        notebook_path: "notebooks/demo.ipynb",
        cell_index: 1,
        new_source: "print('hello')\n",
      },
    },
  );

  assert.deepEqual(
    mapPiToolCallToClaudePayload({
      toolName: "NotebookEdit",
      input: {
        file_path: "notebooks/legacy.ipynb",
        cell_index: 0,
        new_source: "print('legacy')\n",
      },
    }),
    {
      tool_name: "NotebookEdit",
      tool_input: {
        notebook_path: "notebooks/legacy.ipynb",
        cell_index: 0,
        new_source: "print('legacy')\n",
      },
    },
  );
});

test("passes true unknown tools through unchanged", () => {
  const payload = mapPiToolCallToClaudePayload({
    toolName: "custom_preview_tool",
    input: { selector: "#submit" },
  });

  assert.deepEqual(payload, {
    tool_name: "custom_preview_tool",
    tool_input: { selector: "#submit" },
  });
});

test("matcher supports wildcard, alternation, exact, and suffix wildcard", () => {
  assert.equal(matchesClaudeMatcher("*", "Bash"), true);
  assert.equal(matchesClaudeMatcher("Read|Grep|Glob", "Grep"), true);
  assert.equal(matchesClaudeMatcher("Read|Grep|Glob", "Bash"), false);
  assert.equal(matchesClaudeMatcher("Bash", "Bash"), true);
  assert.equal(matchesClaudeMatcher("mcp__playwright__*", "mcp__playwright__browser_click"), true);
  assert.equal(matchesClaudeMatcher("mcp__playwright__*", "mcp__plugin_other__browser_click"), false);
});

test("matcher rejects unsupported wildcard placement", () => {
  assert.throws(
    () => matchesClaudeMatcher("mcp__play*wright__tool", "mcp__playwright__tool"),
    /unsupported position/i,
  );
});
