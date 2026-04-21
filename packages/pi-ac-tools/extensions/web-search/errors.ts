export class WebSearchError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

export class ValidationError extends WebSearchError {}

export class AdapterUnavailableError extends WebSearchError {}

export class BackendExecutionError extends WebSearchError {}

export class ParseError extends WebSearchError {}

export function formatErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
