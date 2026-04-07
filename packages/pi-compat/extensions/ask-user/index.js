import { markPiCompatExtensionInstalled } from "../_shared/install-guard.js";
import { executeAskUserQuestion, normalizeAskUserArguments } from "./runtime.js";

const ASK_USER_PARAMETERS = {
  type: "object",
  properties: {
    header: {
      type: "string",
      description: "Optional heading shown above the question.",
    },
    question: {
      type: "string",
      description: "The prompt to present to the user.",
    },
    options: {
      type: "array",
      description: "Optional single-select or multi-select options.",
      items: {
        anyOf: [
          { type: "string" },
          {
            type: "object",
            properties: {
              label: { type: "string" },
              value: { type: "string" },
              description: { type: "string" },
            },
            required: ["label"],
            additionalProperties: false,
          },
        ],
      },
    },
    multiSelect: {
      type: "boolean",
      description: "Collect multiple options sequentially instead of a single selection.",
    },
    placeholder: {
      type: "string",
      description: "Placeholder text for free-text input prompts.",
    },
    defaultValue: {
      type: "string",
      description: "Default answer to use when nonInteractive is set to default.",
    },
    defaultValues: {
      type: "array",
      description: "Default option values for multi-select prompts when nonInteractive is set to default.",
      items: { type: "string" },
    },
    minSelections: {
      type: "integer",
      description: "Minimum selections required before a multi-select prompt may complete.",
    },
    maxSelections: {
      type: "integer",
      description: "Maximum number of selections to collect for a multi-select prompt.",
    },
    nonInteractive: {
      type: "string",
      enum: ["cancel", "default", "unavailable"],
      description: "How the tool should respond when UI is unavailable. Defaults to unavailable.",
    },
    questions: {
      type: "array",
      description: "Optional batch of prompts to ask sequentially in one tool call.",
      items: {
        type: "object",
        properties: {
          header: { type: "string" },
          question: { type: "string" },
          options: {
            type: "array",
            items: {
              anyOf: [
                { type: "string" },
                {
                  type: "object",
                  properties: {
                    label: { type: "string" },
                    value: { type: "string" },
                    description: { type: "string" },
                  },
                  required: ["label"],
                  additionalProperties: false,
                },
              ],
            },
          },
          multiSelect: { type: "boolean" },
          placeholder: { type: "string" },
          defaultValue: { type: "string" },
          defaultValues: { type: "array", items: { type: "string" } },
          minSelections: { type: "integer" },
          maxSelections: { type: "integer" },
        },
        required: ["question"],
        additionalProperties: false,
      },
    },
  },
  additionalProperties: false,
};

export default function askUserExtension(pi) {
  if (!markPiCompatExtensionInstalled(pi, "ask-user")) {
    return;
  }

  pi.registerTool({
    name: "AskUserQuestion",
    label: "Ask User",
    description: "Collect a structured user decision, selection, or short text answer through the current pi UI.",
    promptSnippet: "Ask the user for explicit approval, a selection, or a short free-text answer when a workflow requires it.",
    promptGuidelines: [
      "Keep prompts concise and concrete.",
      "Use one tool call per decision gate unless a short batched questionnaire is genuinely clearer.",
      "If the result status is cancelled or unavailable, stop and wait for the user instead of guessing.",
    ],
    parameters: ASK_USER_PARAMETERS,
    prepareArguments: normalizeAskUserArguments,
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      return await executeAskUserQuestion(params, ctx);
    },
  });
}
