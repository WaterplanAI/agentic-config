function assertValidMatcherToken(token, matcher) {
  if (token === "") {
    throw new TypeError(`Matcher \"${matcher}\" contains an empty token.`);
  }

  if (token === "*") {
    return;
  }

  const starIndex = token.indexOf("*");
  if (starIndex === -1) {
    return;
  }

  if (starIndex !== token.length - 1) {
    throw new TypeError(
      `Matcher token \"${token}\" in \"${matcher}\" uses \"*\" in an unsupported position. Only suffix wildcards are supported.`,
    );
  }

  if (token.slice(0, -1).includes("*")) {
    throw new TypeError(
      `Matcher token \"${token}\" in \"${matcher}\" contains more than one wildcard. Only one trailing wildcard is supported.`,
    );
  }
}

export function parseClaudeMatcher(matcher) {
  if (typeof matcher !== "string" || matcher.trim() === "") {
    throw new TypeError("Matcher must be a non-empty string.");
  }

  const tokens = matcher
    .split("|")
    .map((token) => token.trim())
    .filter((token) => token !== "");

  if (tokens.length === 0) {
    throw new TypeError(`Matcher \"${matcher}\" does not include any tokens.`);
  }

  for (const token of tokens) {
    assertValidMatcherToken(token, matcher);
  }

  return tokens;
}

function tokenMatchesToolName(token, toolName) {
  if (token === "*") {
    return true;
  }

  if (token.endsWith("*")) {
    return toolName.startsWith(token.slice(0, -1));
  }

  return token === toolName;
}

export function matchesClaudeMatcher(matcher, toolName) {
  if (typeof toolName !== "string" || toolName.trim() === "") {
    throw new TypeError("toolName must be a non-empty string.");
  }

  const parsedMatcher = parseClaudeMatcher(matcher);
  return parsedMatcher.some((token) => tokenMatchesToolName(token, toolName));
}
