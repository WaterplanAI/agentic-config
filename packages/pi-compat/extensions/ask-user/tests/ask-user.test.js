import assert from "node:assert/strict";
import test from "node:test";

import { executeAskUserQuestion, normalizeAskUserArguments } from "../runtime.js";

function createInteractiveContext({ selections = [], inputs = [] } = {}) {
  const selectionQueue = [...selections];
  const inputQueue = [...inputs];

  return {
    hasUI: true,
    ui: {
      async select() {
        return selectionQueue.shift();
      },
      async input() {
        return inputQueue.shift();
      },
    },
  };
}

test("normalizes a legacy single-question call into the shared questions shape", () => {
  const normalized = normalizeAskUserArguments({
    header: "Gate 1",
    question: "Apply changes?",
    options: [
      { label: "Yes", description: "Proceed" },
      { label: "No", description: "Abort" },
    ],
  });

  assert.equal(normalized.nonInteractive, "unavailable");
  assert.equal(normalized.questions.length, 1);
  assert.equal(normalized.questions[0].header, "Gate 1");
  assert.equal(normalized.questions[0].question, "Apply changes?");
  assert.deepEqual(
    normalized.questions[0].options.map((option) => option.label),
    ["Yes", "No"],
  );
});

test("executes sequential select and input prompts through the current UI", async () => {
  const result = await executeAskUserQuestion(
    {
      questions: [
        {
          header: "Gate 1",
          question: "Apply changes?",
          options: [{ label: "Yes" }, { label: "No" }],
        },
        {
          header: "Project",
          question: "Project ID",
          placeholder: "example-prod",
        },
      ],
    },
    createInteractiveContext({
      selections: ["Yes"],
      inputs: ["example-prod"],
    }),
  );

  assert.equal(result.details.status, "answered");
  assert.equal(result.details.answers.length, 2);
  assert.equal(result.details.answers[0].selectedOptions[0].label, "Yes");
  assert.equal(result.details.answers[1].text, "example-prod");
});

test("disambiguates duplicate rendered option labels", async () => {
  const result = await executeAskUserQuestion(
    {
      question: "Which project should be used?",
      options: [
        { label: "Example", value: "one" },
        { label: "Example", value: "two" },
      ],
    },
    createInteractiveContext({
      selections: ["Example [2]"],
    }),
  );

  assert.equal(result.details.status, "answered");
  assert.equal(result.details.answers[0].selectedOptions[0].value, "two");
});

test("supports bounded multi-select prompts", async () => {
  const result = await executeAskUserQuestion(
    {
      question: "Which package managers should be configured?",
      multiSelect: true,
      minSelections: 1,
      maxSelections: 2,
      options: ["pnpm", "bun", "uv"],
    },
    createInteractiveContext({
      selections: ["pnpm", "uv"],
    }),
  );

  assert.equal(result.details.status, "answered");
  assert.equal(result.details.answers[0].selectedOptions.length, 2);
  assert.deepEqual(
    result.details.answers[0].selectedOptions.map((option) => option.label),
    ["pnpm", "uv"],
  );
});

test("keeps the synthetic finish action distinct from user-provided option labels", async () => {
  const result = await executeAskUserQuestion(
    {
      question: "Pick options",
      multiSelect: true,
      minSelections: 1,
      options: ["Finish selection (no selections yet)", "Actual option"],
    },
    createInteractiveContext({
      selections: ["Finish selection (no selections yet)", "Finish selection (1 selected)"],
    }),
  );

  assert.equal(result.details.status, "answered");
  assert.deepEqual(
    result.details.answers[0].selectedOptions.map((option) => option.label),
    ["Finish selection (no selections yet)"],
  );
});

test("inherits shared multi-select bounds across batched questions", () => {
  const normalized = normalizeAskUserArguments({
    multiSelect: true,
    minSelections: 2,
    maxSelections: 3,
    options: ["pnpm", "bun", "uv"],
    questions: [
      {
        question: "Managers",
      },
    ],
  });

  assert.equal(normalized.questions[0].minSelections, 2);
  assert.equal(normalized.questions[0].maxSelections, 3);
});

test("returns an unavailable result when UI is missing and no defaults are allowed", async () => {
  const result = await executeAskUserQuestion(
    {
      question: "Apply changes?",
      options: ["Yes", "No"],
    },
    {
      hasUI: false,
    },
  );

  assert.equal(result.details.status, "unavailable");
  assert.match(result.content[0].text, /Stop and ask the user in chat/i);
});

test("uses configured defaults when nonInteractive is set to default", async () => {
  const result = await executeAskUserQuestion(
    {
      question: "Apply changes?",
      options: ["Yes", "No"],
      defaultValue: "No",
      nonInteractive: "default",
    },
    {
      hasUI: false,
    },
  );

  assert.equal(result.details.status, "answered");
  assert.equal(result.details.answers[0].selectedOptions[0].label, "No");
});

test("returns unavailable when a select prompt has no valid default option", async () => {
  const result = await executeAskUserQuestion(
    {
      question: "Apply changes?",
      options: ["Yes", "No"],
      defaultValue: "Later",
      nonInteractive: "default",
    },
    {
      hasUI: false,
    },
  );

  assert.equal(result.details.status, "unavailable");
  assert.match(result.content[0].text, /no valid default option/i);
});

test("returns unavailable when multi-select defaults do not satisfy the configured bounds", async () => {
  const result = await executeAskUserQuestion(
    {
      question: "Which package managers should be configured?",
      options: ["pnpm", "bun", "uv"],
      multiSelect: true,
      minSelections: 2,
      defaultValues: ["pnpm"],
      nonInteractive: "default",
    },
    {
      hasUI: false,
    },
  );

  assert.equal(result.details.status, "unavailable");
  assert.match(result.content[0].text, /no valid default option/i);
});
