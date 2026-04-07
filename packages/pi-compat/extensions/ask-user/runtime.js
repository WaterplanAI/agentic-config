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
    throw new TypeError(`AskUserQuestion requires a non-empty ${fieldName}.`);
  }
  return normalized;
}

function normalizeInteger(value, fieldName, fallback) {
  if (value === undefined || value === null) {
    return fallback;
  }

  if (!Number.isInteger(value)) {
    throw new TypeError(`AskUserQuestion expected ${fieldName} to be an integer.`);
  }

  return value;
}

function normalizeOption(option, index) {
  if (typeof option === "string") {
    const label = normalizeRequiredString(option, `options[${index}]`);
    return {
      label,
      value: label,
      description: undefined,
    };
  }

  if (!isObject(option)) {
    throw new TypeError(`AskUserQuestion option ${index} must be a string or object.`);
  }

  const label = normalizeRequiredString(option.label ?? option.value, `options[${index}].label`);
  return {
    label,
    value: normalizeOptionalString(option.value) ?? label,
    description: normalizeOptionalString(option.description),
  };
}

function normalizeQuestion(question, index, inheritedDefaults) {
  if (!isObject(question)) {
    throw new TypeError(`AskUserQuestion question ${index} must be an object.`);
  }

  const optionsInput = question.options ?? inheritedDefaults.options;
  const options = Array.isArray(optionsInput) ? optionsInput.map(normalizeOption) : [];
  const multiSelect = Boolean(question.multiSelect ?? inheritedDefaults.multiSelect ?? false);
  const minSelections = Math.max(
    0,
    normalizeInteger(question.minSelections ?? inheritedDefaults.minSelections, `questions[${index}].minSelections`, 0),
  );
  const maxSelectionsRaw = normalizeInteger(
    question.maxSelections ?? inheritedDefaults.maxSelections,
    `questions[${index}].maxSelections`,
    undefined,
  );
  const maxSelections = maxSelectionsRaw === undefined ? undefined : Math.max(minSelections, maxSelectionsRaw);

  if (multiSelect && options.length === 0) {
    throw new TypeError(`AskUserQuestion question ${index} uses multiSelect but provides no options.`);
  }

  return {
    header: normalizeOptionalString(question.header ?? inheritedDefaults.header),
    question: normalizeRequiredString(question.question ?? inheritedDefaults.question, `questions[${index}].question`),
    options,
    multiSelect,
    placeholder: normalizeOptionalString(question.placeholder ?? inheritedDefaults.placeholder),
    defaultValue: normalizeOptionalString(question.defaultValue ?? inheritedDefaults.defaultValue),
    defaultValues: Array.isArray(question.defaultValues ?? inheritedDefaults.defaultValues)
      ? (question.defaultValues ?? inheritedDefaults.defaultValues).map((value, valueIndex) =>
          normalizeRequiredString(value, `questions[${index}].defaultValues[${valueIndex}]`),
        )
      : [],
    minSelections,
    maxSelections,
  };
}

export function normalizeAskUserArguments(args) {
  if (!isObject(args)) {
    throw new TypeError("AskUserQuestion requires an object of arguments.");
  }

  const inheritedDefaults = {
    header: args.header,
    question: args.question,
    options: args.options,
    multiSelect: args.multiSelect,
    placeholder: args.placeholder,
    defaultValue: args.defaultValue,
    defaultValues: args.defaultValues,
    minSelections: args.minSelections,
    maxSelections: args.maxSelections,
  };

  const questions = Array.isArray(args.questions) && args.questions.length > 0
    ? args.questions.map((question, index) => normalizeQuestion(question, index, inheritedDefaults))
    : [normalizeQuestion(args, 0, inheritedDefaults)];

  const nonInteractive = normalizeOptionalString(args.nonInteractive)?.toLowerCase() ?? "unavailable";
  if (!["cancel", "default", "unavailable"].includes(nonInteractive)) {
    throw new TypeError("AskUserQuestion nonInteractive must be one of: cancel, default, unavailable.");
  }

  return {
    questions,
    nonInteractive,
  };
}

function formatOption(option) {
  return option.description ? `${option.label} -- ${option.description}` : option.label;
}

function buildMenuEntries(options, reservedLabels = []) {
  const usedLabels = new Set(reservedLabels);

  return options.map((option, index) => {
    const baseLabel = formatOption(option);
    let display = baseLabel;
    let suffix = 2;

    while (usedLabels.has(display)) {
      display = `${baseLabel} [${suffix}]`;
      suffix += 1;
    }

    usedLabels.add(display);
    return {
      display,
      option,
      index,
    };
  });
}

function buildUniqueDoneLabel(selectedCount, reservedLabels) {
  const baseLabel = selectedCount === 0 ? "Finish selection (no selections yet)" : `Finish selection (${selectedCount} selected)`;
  const usedLabels = new Set(reservedLabels);
  let display = baseLabel;
  let suffix = 2;

  while (usedLabels.has(display)) {
    display = `${baseLabel} [${suffix}]`;
    suffix += 1;
  }

  return display;
}

function buildPromptTitle(question, index, total, suffix) {
  const parts = [];
  if (question.header) {
    parts.push(question.header);
  }
  if (total > 1) {
    parts.push(`Question ${index + 1}/${total}`);
  }
  parts.push(question.question);
  if (suffix) {
    parts.push(suffix);
  }
  return parts.join(" | ");
}

function findDefaultSingleOption(question) {
  if (!question.defaultValue) {
    return undefined;
  }

  return question.options.find((option) => option.value === question.defaultValue || option.label === question.defaultValue);
}

function findDefaultMultiOptions(question) {
  if (question.defaultValues.length === 0) {
    return [];
  }

  return question.defaultValues
    .map((value) => question.options.find((option) => option.value === value || option.label === value))
    .filter(Boolean);
}

function buildUnavailableAnswer(question, index, reason) {
  return {
    status: "unavailable",
    index,
    header: question.header,
    question: question.question,
    responseType: question.multiSelect ? "multi_select" : question.options.length > 0 ? "select" : "input",
    reason,
  };
}

function buildCancelledAnswer(question, index, reason) {
  return {
    status: "cancelled",
    index,
    header: question.header,
    question: question.question,
    responseType: question.multiSelect ? "multi_select" : question.options.length > 0 ? "select" : "input",
    reason,
  };
}

function buildInputAnswer(question, index, text) {
  return {
    status: "answered",
    index,
    header: question.header,
    question: question.question,
    responseType: "input",
    text,
  };
}

function buildSelectAnswer(question, index, selectedOptions) {
  return {
    status: "answered",
    index,
    header: question.header,
    question: question.question,
    responseType: question.multiSelect ? "multi_select" : "select",
    selectedOptions: selectedOptions.map((option) => ({
      label: option.label,
      value: option.value,
      description: option.description,
    })),
  };
}

function resolveNonInteractiveAnswer(question, index, nonInteractive) {
  if (nonInteractive === "cancel") {
    return buildCancelledAnswer(question, index, "Interactive UI is unavailable in the current runtime.");
  }

  if (nonInteractive === "default") {
    if (question.options.length > 0) {
      const defaults = question.multiSelect ? findDefaultMultiOptions(question) : [findDefaultSingleOption(question)].filter(Boolean);
      if (
        defaults.length > 0 &&
        defaults.length >= question.minSelections &&
        (question.maxSelections === undefined || defaults.length <= question.maxSelections)
      ) {
        return buildSelectAnswer(question, index, defaults);
      }

      return buildUnavailableAnswer(
        question,
        index,
        "Interactive UI is unavailable and no valid default option was configured. Stop and ask the user in chat.",
      );
    }

    if (question.defaultValue) {
      return buildInputAnswer(question, index, question.defaultValue);
    }
  }

  return buildUnavailableAnswer(question, index, "Interactive UI is unavailable in the current runtime. Stop and ask the user in chat.");
}

async function askInputQuestion(question, index, total, ctx) {
  const title = buildPromptTitle(question, index, total);
  const response = await ctx.ui.input(title, question.placeholder);
  if (response === undefined) {
    return buildCancelledAnswer(question, index, "The user dismissed the prompt without providing an answer.");
  }

  return buildInputAnswer(question, index, response);
}

async function askSelectQuestion(question, index, total, ctx) {
  const entries = buildMenuEntries(question.options);
  const choice = await ctx.ui.select(
    buildPromptTitle(question, index, total),
    entries.map((entry) => entry.display),
  );
  if (choice === undefined) {
    return buildCancelledAnswer(question, index, "The user dismissed the selection prompt.");
  }

  const selectedEntry = entries.find((entry) => entry.display === choice);
  if (!selectedEntry) {
    return buildCancelledAnswer(question, index, `The selected option could not be resolved: ${choice}`);
  }

  return buildSelectAnswer(question, index, [selectedEntry.option]);
}

async function askMultiSelectQuestion(question, index, total, ctx) {
  const selectedIndexes = [];

  while (true) {
    const remainingEntries = buildMenuEntries(
      question.options
        .map((option, optionIndex) => ({ option, optionIndex }))
        .filter(({ optionIndex }) => !selectedIndexes.includes(optionIndex))
        .map(({ option }) => option),
    ).map((entry, localIndex) => ({
      ...entry,
      optionIndex: question.options.findIndex((option, optionIndex) => {
        return !selectedIndexes.includes(optionIndex) && option === entry.option;
      }),
      localIndex,
    }));

    const doneLabel = buildUniqueDoneLabel(
      selectedIndexes.length,
      remainingEntries.map((entry) => entry.display),
    );
    const menuOptions = [...remainingEntries.map((entry) => entry.display), doneLabel];

    const suffix = selectedIndexes.length > 0
      ? `Selected: ${selectedIndexes.map((optionIndex) => question.options[optionIndex].label).join(", ")}`
      : "Select one option at a time.";

    const choice = await ctx.ui.select(buildPromptTitle(question, index, total, suffix), menuOptions);
    if (choice === undefined) {
      return buildCancelledAnswer(question, index, "The user dismissed the multi-select prompt.");
    }

    if (choice === doneLabel) {
      if (selectedIndexes.length < question.minSelections) {
        return buildCancelledAnswer(
          question,
          index,
          `At least ${question.minSelections} option(s) were required before completing the prompt.`,
        );
      }

      return buildSelectAnswer(
        question,
        index,
        selectedIndexes.map((optionIndex) => question.options[optionIndex]),
      );
    }

    const selectedEntry = remainingEntries.find((entry) => entry.display === choice);
    if (!selectedEntry || selectedEntry.optionIndex === -1) {
      return buildCancelledAnswer(question, index, `The selected option could not be resolved: ${choice}`);
    }

    selectedIndexes.push(selectedEntry.optionIndex);
    if (question.maxSelections !== undefined && selectedIndexes.length >= question.maxSelections) {
      return buildSelectAnswer(
        question,
        index,
        selectedIndexes.map((optionIndex) => question.options[optionIndex]),
      );
    }
  }
}

function summarizeAnswer(answer) {
  const prefix = answer.header ? `${answer.header}: ` : "";

  if (answer.status === "answered") {
    if (answer.responseType === "input") {
      return `${prefix}${answer.question} -> ${answer.text}`;
    }

    const selected = answer.selectedOptions.map((option) => option.label).join(", ");
    return `${prefix}${answer.question} -> ${selected}`;
  }

  return `${prefix}${answer.question} -> ${answer.reason}`;
}

function buildResult(status, answers) {
  const lines = [];

  if (status === "answered") {
    lines.push("AskUserQuestion completed.");
  } else if (status === "cancelled") {
    lines.push("AskUserQuestion cancelled.");
  } else {
    lines.push("AskUserQuestion unavailable.");
  }

  for (const answer of answers) {
    lines.push(`- ${summarizeAnswer(answer)}`);
  }

  if (status !== "answered") {
    lines.push("Next step: stop and ask the user in chat before continuing.");
  }

  return {
    content: [{ type: "text", text: lines.join("\n") }],
    details: {
      status,
      answers,
    },
  };
}

export async function executeAskUserQuestion(args, ctx) {
  const normalized = normalizeAskUserArguments(args);
  const answers = [];

  for (const [index, question] of normalized.questions.entries()) {
    let answer;
    if (!ctx?.hasUI || !ctx?.ui) {
      answer = resolveNonInteractiveAnswer(question, index, normalized.nonInteractive);
    } else if (question.options.length === 0) {
      answer = await askInputQuestion(question, index, normalized.questions.length, ctx);
    } else if (question.multiSelect) {
      answer = await askMultiSelectQuestion(question, index, normalized.questions.length, ctx);
    } else {
      answer = await askSelectQuestion(question, index, normalized.questions.length, ctx);
    }

    answers.push(answer);
    if (answer.status !== "answered") {
      return buildResult(answer.status, answers);
    }
  }

  return buildResult("answered", answers);
}
