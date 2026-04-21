import type { AppliedWebSearchRequest, BackendName, ContextThresholdMode, LocationContext } from "./types.js";
import { ValidationError } from "./errors.js";

export const REQUEST_DEFAULTS = {
  count: 5,
  maximum_number_of_urls: 5,
  maximum_number_of_tokens: 2048,
  maximum_number_of_snippets: 10,
  maximum_number_of_tokens_per_url: 1024,
  maximum_number_of_snippets_per_url: 5,
  context_threshold_mode: "strict" as ContextThresholdMode,
};

const CONTROL_CHAR_REGEX = /[\u0000-\u001F\u007F-\u009F]/;
const WHITESPACE_REGEX = /\s+/g;

export function applyDefaultsAndValidate(rawParams: Record<string, unknown>): AppliedWebSearchRequest {
  const q = sanitizeQuery(rawParams.q);

  const request: AppliedWebSearchRequest = {
    q,
    count: integerInRange(rawParams.count, REQUEST_DEFAULTS.count, 1, 50, "count"),
    maximum_number_of_urls: integerInRange(
      rawParams.maximum_number_of_urls,
      REQUEST_DEFAULTS.maximum_number_of_urls,
      1,
      50,
      "maximum_number_of_urls",
    ),
    maximum_number_of_tokens: integerInRange(
      rawParams.maximum_number_of_tokens,
      REQUEST_DEFAULTS.maximum_number_of_tokens,
      1024,
      32768,
      "maximum_number_of_tokens",
    ),
    maximum_number_of_snippets: integerInRange(
      rawParams.maximum_number_of_snippets,
      REQUEST_DEFAULTS.maximum_number_of_snippets,
      1,
      100,
      "maximum_number_of_snippets",
    ),
    maximum_number_of_tokens_per_url: integerInRange(
      rawParams.maximum_number_of_tokens_per_url,
      REQUEST_DEFAULTS.maximum_number_of_tokens_per_url,
      512,
      8192,
      "maximum_number_of_tokens_per_url",
    ),
    maximum_number_of_snippets_per_url: integerInRange(
      rawParams.maximum_number_of_snippets_per_url,
      REQUEST_DEFAULTS.maximum_number_of_snippets_per_url,
      1,
      100,
      "maximum_number_of_snippets_per_url",
    ),
    context_threshold_mode: contextThresholdMode(
      rawParams.context_threshold_mode,
      REQUEST_DEFAULTS.context_threshold_mode,
    ),
  };

  const country = sanitizeOptionalString(rawParams.country, "country", 64);
  if (country) request.country = country;

  const searchLang = sanitizeOptionalString(rawParams.search_lang, "search_lang", 64);
  if (searchLang) request.search_lang = searchLang;

  const freshness = sanitizeOptionalString(rawParams.freshness, "freshness", 128);
  if (freshness) request.freshness = freshness;

  if (rawParams.enable_local !== undefined) {
    if (typeof rawParams.enable_local !== "boolean") {
      throw new ValidationError("enable_local must be a boolean when provided.");
    }
    request.enable_local = rawParams.enable_local;
  }

  const goggles = normalizeGoggles(rawParams.goggles);
  if (goggles.length > 0) {
    request.goggles = goggles;
  }

  const location = normalizeLocation(rawParams.location);
  if (location) {
    request.location = location;
  }

  return request;
}

export function createRequestCacheKey(request: AppliedWebSearchRequest, defaultBackend: BackendName): string {
  return JSON.stringify(sortValue({ default_backend: defaultBackend, request }));
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortValue);
  }

  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value as Record<string, unknown>)
      .filter(([, childValue]) => childValue !== undefined)
      .sort(([a], [b]) => a.localeCompare(b))) {
      out[key] = sortValue(child);
    }
    return out;
  }

  return value;
}

function sanitizeQuery(value: unknown): string {
  if (typeof value !== "string") {
    throw new ValidationError("q must be a string.");
  }

  const normalized = normalizeFreeText(value);
  if (!normalized) {
    throw new ValidationError("q must not be empty.");
  }

  if (normalized.length > 400) {
    throw new ValidationError("q must be 400 characters or fewer.");
  }

  const words = normalized.split(/\s+/).filter(Boolean);
  if (words.length > 50) {
    throw new ValidationError("q must be 50 words or fewer.");
  }

  return normalized;
}

function integerInRange(
  value: unknown,
  defaultValue: number,
  min: number,
  max: number,
  field: string,
): number {
  const next = value === undefined ? defaultValue : Number(value);
  if (!Number.isInteger(next) || next < min || next > max) {
    throw new ValidationError(`${field} must be an integer between ${min} and ${max}.`);
  }
  return next;
}

function contextThresholdMode(value: unknown, defaultValue: ContextThresholdMode): ContextThresholdMode {
  const next = value === undefined ? defaultValue : String(value).trim().toLowerCase();
  if (next === "strict" || next === "balanced" || next === "lenient" || next === "disabled") {
    return next;
  }
  throw new ValidationError("context_threshold_mode must be one of: strict, balanced, lenient, disabled.");
}

function sanitizeOptionalString(value: unknown, field: string, maxLength: number): string | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value !== "string") {
    throw new ValidationError(`${field} must be a string when provided.`);
  }

  const normalized = normalizeTightText(value, field);
  if (!normalized) {
    throw new ValidationError(`${field} must not be empty when provided.`);
  }
  if (normalized.length > maxLength) {
    throw new ValidationError(`${field} must be ${maxLength} characters or fewer.`);
  }
  return normalized;
}

function normalizeGoggles(value: unknown): string[] {
  if (value === undefined || value === null) {
    return [];
  }

  const rawValues = Array.isArray(value) ? value : [value];
  const out: string[] = [];
  const seen = new Set<string>();

  for (const raw of rawValues) {
    if (typeof raw !== "string") {
      throw new ValidationError("goggles must be a string or an array of strings.");
    }
    const normalized = normalizeTightText(raw, "goggles");
    if (!normalized) {
      continue;
    }
    if (normalized.length > 512) {
      throw new ValidationError("Each goggles entry must be 512 characters or fewer.");
    }
    if (seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    out.push(normalized);
  }

  return out;
}

function normalizeLocation(value: unknown): LocationContext | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new ValidationError("location must be an object when provided.");
  }

  const locationValue = value as Record<string, unknown>;
  const location: LocationContext = {};

  if (locationValue.lat !== undefined) {
    const lat = Number(locationValue.lat);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      throw new ValidationError("location.lat must be between -90 and 90.");
    }
    location.lat = lat;
  }

  if (locationValue.long !== undefined) {
    const long = Number(locationValue.long);
    if (!Number.isFinite(long) || long < -180 || long > 180) {
      throw new ValidationError("location.long must be between -180 and 180.");
    }
    location.long = long;
  }

  const city = sanitizeOptionalLocationString(locationValue.city, "location.city");
  if (city) location.city = city;

  const state = sanitizeOptionalLocationString(locationValue.state, "location.state");
  if (state) location.state = state;

  const stateName = sanitizeOptionalLocationString(locationValue.state_name, "location.state_name");
  if (stateName) location.state_name = stateName;

  const country = sanitizeOptionalLocationString(locationValue.country, "location.country");
  if (country) location.country = country;

  const postalCode = sanitizeOptionalLocationString(locationValue.postal_code, "location.postal_code");
  if (postalCode) location.postal_code = postalCode;

  return Object.keys(location).length > 0 ? location : undefined;
}

function sanitizeOptionalLocationString(value: unknown, field: string): string | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value !== "string") {
    throw new ValidationError(`${field} must be a string when provided.`);
  }
  const normalized = normalizeTightText(value, field);
  if (!normalized) {
    throw new ValidationError(`${field} must not be empty when provided.`);
  }
  if (normalized.length > 128) {
    throw new ValidationError(`${field} must be 128 characters or fewer.`);
  }
  return normalized;
}

function normalizeFreeText(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/[\u0000-\u001F\u007F-\u009F]+/g, " ")
    .replace(WHITESPACE_REGEX, " ")
    .trim();
}

function normalizeTightText(value: string, field: string): string {
  const normalized = value.normalize("NFKC");
  if (CONTROL_CHAR_REGEX.test(normalized)) {
    throw new ValidationError(`${field} contains unsupported control characters.`);
  }
  return normalized.replace(WHITESPACE_REGEX, " ").trim();
}
