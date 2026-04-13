import type {
  AppliedWebSearchRequest,
  GroundingGenericItem,
  GroundingMapItem,
  GroundingPoiItem,
  NormalizedSearchResult,
  SourceMetadata,
} from "./types.js";
import { ParseError } from "./errors.js";

export const WEB_SEARCH_CONTEXT_START = "UNTRUSTED_WEB_SEARCH_CONTEXT";
export const WEB_SEARCH_CONTEXT_END = "END_UNTRUSTED_WEB_SEARCH_CONTEXT";

const ZERO_WIDTH_REGEX = /[\u200B-\u200D\uFEFF]/g;
const BIDI_REGEX = /[\u202A-\u202E\u2066-\u2069]/g;
const CONTROL_REGEX = /[\u0000-\u001F\u007F-\u009F]/g;
const ANSI_REGEX = /\u001B\[[0-9;]*m/g;

interface SnippetBudget {
  totalCharsRemaining: number;
  totalSnippetsRemaining: number;
}

export function stripAnsi(input: string): string {
  return input.replace(ANSI_REGEX, "");
}

export function truncateText(input: string, maxLength: number): string {
  if (maxLength <= 0) {
    return "";
  }
  if (input.length <= maxLength) {
    return input;
  }
  const head = input.slice(0, Math.max(0, maxLength - 1)).trimEnd();
  return `${head}…`;
}

export function sanitizeExternalText(value: unknown, maxLength = 2000): string {
  const input = typeof value === "string" ? value : String(value ?? "");
  const normalized = input
    .normalize("NFKC")
    .replace(ZERO_WIDTH_REGEX, "")
    .replace(BIDI_REGEX, "")
    .replace(CONTROL_REGEX, " ")
    .replace(/\s+/g, " ")
    .trim();

  const escaped = normalized
    .replaceAll(WEB_SEARCH_CONTEXT_START, "[UNTRUSTED_WEB_SEARCH_CONTEXT]")
    .replaceAll(WEB_SEARCH_CONTEXT_END, "[END_UNTRUSTED_WEB_SEARCH_CONTEXT]");

  return truncateText(escaped, maxLength);
}

export function sanitizeUrl(value: unknown): string | null {
  try {
    const input = String(value ?? "").trim();
    if (!input) {
      return null;
    }

    const url = new URL(input);
    if (url.protocol !== "https:" && url.protocol !== "http:") {
      return null;
    }

    const hostname = url.hostname.toLowerCase();
    if (
      !hostname ||
      hostname === "localhost" ||
      hostname === "127.0.0.1" ||
      hostname === "::1" ||
      hostname.endsWith(".localhost") ||
      hostname.endsWith(".local")
    ) {
      return null;
    }

    return url.toString();
  } catch {
    return null;
  }
}

export function hostnameFromUrl(url: string): string | undefined {
  try {
    return new URL(url).hostname;
  } catch {
    return undefined;
  }
}

export function parseJsonObjectFromText(text: string): unknown {
  const cleaned = stripAnsi(text).trim();
  if (!cleaned) {
    throw new ParseError("Backend returned empty output.");
  }

  const direct = tryParseObject(cleaned);
  if (direct !== undefined) {
    return direct;
  }

  const fencedMatches = cleaned.matchAll(/```(?:json)?\s*([\s\S]*?)```/gi);
  for (const match of fencedMatches) {
    const candidate = match[1]?.trim();
    if (!candidate) {
      continue;
    }
    const parsed = tryParseObject(candidate);
    if (parsed !== undefined) {
      return parsed;
    }
  }

  const balancedCandidates = extractBalancedJsonObjects(cleaned);
  for (const candidate of balancedCandidates) {
    const parsed = tryParseObject(candidate);
    if (parsed !== undefined) {
      return parsed;
    }
  }

  throw new ParseError("Backend returned unparseable JSON.");
}

export function normalizeResultShape(
  raw: unknown,
  request: AppliedWebSearchRequest,
): NormalizedSearchResult {
  const root = asRecord(raw);
  if (!("grounding" in root) && !("sources" in root)) {
    throw new ParseError("Backend output did not match the normalized web-search shape.");
  }

  const grounding = asRecord(root.grounding);
  const sourceMap = normalizeSourceMap(root.sources);
  const maxItems = Math.min(request.count, request.maximum_number_of_urls);
  const budget: SnippetBudget = {
    totalCharsRemaining: request.maximum_number_of_tokens * 4,
    totalSnippetsRemaining: request.maximum_number_of_snippets,
  };

  const generic = normalizeGenericItems(grounding.generic, sourceMap, request, budget).slice(0, maxItems);
  const poi = normalizePoiItem(grounding.poi, sourceMap, request, budget);
  const map = normalizeMapItems(grounding.map, sourceMap, request, budget).slice(0, maxItems);
  const filteredSources = buildFilteredSourceMap(sourceMap, generic, poi, map);

  return {
    grounding: {
      generic,
      poi,
      map,
    },
    sources: filteredSources,
  };
}

function tryParseObject(text: string): unknown | undefined {
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === "object") {
      return parsed;
    }
  } catch {
    // Ignore parse failures; callers try additional extraction strategies.
  }
  return undefined;
}

function extractBalancedJsonObjects(text: string): string[] {
  const candidates: string[] = [];

  for (let start = 0; start < text.length; start += 1) {
    if (text[start] !== "{") {
      continue;
    }

    let depth = 0;
    let inString = false;
    let escaping = false;

    for (let index = start; index < text.length; index += 1) {
      const char = text[index];

      if (inString) {
        if (escaping) {
          escaping = false;
        } else if (char === "\\") {
          escaping = true;
        } else if (char === '"') {
          inString = false;
        }
        continue;
      }

      if (char === '"') {
        inString = true;
        continue;
      }

      if (char === "{") {
        depth += 1;
        continue;
      }

      if (char === "}") {
        depth -= 1;
        if (depth === 0) {
          candidates.push(text.slice(start, index + 1));
          break;
        }
      }
    }
  }

  return candidates.sort((a, b) => b.length - a.length);
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function normalizeSourceMap(value: unknown): Record<string, SourceMetadata> {
  const out: Record<string, SourceMetadata> = {};
  const sourceEntries = asRecord(value);

  for (const [rawUrl, rawMetadata] of Object.entries(sourceEntries)) {
    const url = sanitizeUrl(rawUrl);
    if (!url) {
      continue;
    }

    const metadata = asRecord(rawMetadata);
    const title = sanitizeExternalText(metadata.title, 200) || undefined;
    const hostname =
      sanitizeExternalText(metadata.hostname, 120) ||
      hostnameFromUrl(url);
    const age = normalizeAge(metadata.age);

    out[url] = {
      ...(title ? { title } : {}),
      ...(hostname ? { hostname } : {}),
      age,
    };
  }

  return out;
}

function normalizeAge(value: unknown): string[] | null {
  if (Array.isArray(value)) {
    const items = value.map((item) => sanitizeExternalText(item, 80)).filter(Boolean);
    return items.length > 0 ? items : null;
  }

  if (typeof value === "string") {
    const item = sanitizeExternalText(value, 80);
    return item ? [item] : null;
  }

  return null;
}

function normalizeGenericItems(
  value: unknown,
  sourceMap: Record<string, SourceMetadata>,
  request: AppliedWebSearchRequest,
  budget: SnippetBudget,
): GroundingGenericItem[] {
  const rawItems = Array.isArray(value) ? value : [];
  const out: GroundingGenericItem[] = [];
  const seen = new Set<string>();

  for (const item of rawItems) {
    const record = asRecord(item);
    const url = sanitizeUrl(record.url);
    if (!url || seen.has(url)) {
      continue;
    }

    seen.add(url);
    const fallbackTitle = sourceMap[url]?.title || hostnameFromUrl(url) || "Untitled result";
    const title = sanitizeExternalText(record.title || fallbackTitle, 200) || fallbackTitle;
    const snippets = budgetSnippets(toSnippetArray(record.snippets), request, budget);

    out.push({ url, title, snippets });
  }

  return out;
}

function normalizePoiItem(
  value: unknown,
  sourceMap: Record<string, SourceMetadata>,
  request: AppliedWebSearchRequest,
  budget: SnippetBudget,
): GroundingPoiItem | null {
  if (value === undefined || value === null) {
    return null;
  }

  const record = asRecord(value);
  const url = sanitizeUrl(record.url) || undefined;
  const name = sanitizeExternalText(record.name, 120) || undefined;
  const title =
    sanitizeExternalText(record.title || name || (url ? sourceMap[url]?.title : ""), 200) ||
    undefined;
  const snippets = budgetSnippets(toSnippetArray(record.snippets), request, budget);

  if (!url && !name && !title && snippets.length === 0) {
    return null;
  }

  return {
    ...(name ? { name } : {}),
    ...(url ? { url } : {}),
    ...(title ? { title } : {}),
    ...(snippets.length > 0 ? { snippets } : {}),
  };
}

function normalizeMapItems(
  value: unknown,
  sourceMap: Record<string, SourceMetadata>,
  request: AppliedWebSearchRequest,
  budget: SnippetBudget,
): GroundingMapItem[] {
  const rawItems = Array.isArray(value) ? value : [];
  const out: GroundingMapItem[] = [];
  const seen = new Set<string>();

  for (const item of rawItems) {
    const record = asRecord(item);
    const url = sanitizeUrl(record.url) || undefined;
    const dedupeKey = url || sanitizeExternalText(record.name || record.title, 80);
    if (!dedupeKey || seen.has(dedupeKey)) {
      continue;
    }
    seen.add(dedupeKey);

    const name = sanitizeExternalText(record.name, 120) || undefined;
    const title =
      sanitizeExternalText(record.title || name || (url ? sourceMap[url]?.title : ""), 200) ||
      undefined;
    const snippets = budgetSnippets(toSnippetArray(record.snippets), request, budget);

    if (!url && !name && !title && snippets.length === 0) {
      continue;
    }

    out.push({
      ...(name ? { name } : {}),
      ...(url ? { url } : {}),
      ...(title ? { title } : {}),
      ...(snippets.length > 0 ? { snippets } : {}),
    });
  }

  return out;
}

function toSnippetArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeExternalText(item, 1200)).filter(Boolean);
  }

  if (typeof value === "string") {
    const snippet = sanitizeExternalText(value, 1200);
    return snippet ? [snippet] : [];
  }

  return [];
}

function budgetSnippets(
  snippets: string[],
  request: AppliedWebSearchRequest,
  budget: SnippetBudget,
): string[] {
  const out: string[] = [];
  let perUrlCharsRemaining = request.maximum_number_of_tokens_per_url * 4;

  for (const snippet of snippets.slice(0, request.maximum_number_of_snippets_per_url)) {
    if (budget.totalSnippetsRemaining <= 0 || budget.totalCharsRemaining <= 0 || perUrlCharsRemaining <= 0) {
      break;
    }

    const maxChars = Math.min(perUrlCharsRemaining, budget.totalCharsRemaining, 1200);
    const nextSnippet = truncateText(snippet, maxChars);
    if (!nextSnippet) {
      continue;
    }

    out.push(nextSnippet);
    perUrlCharsRemaining -= nextSnippet.length;
    budget.totalCharsRemaining -= nextSnippet.length;
    budget.totalSnippetsRemaining -= 1;
  }

  return out;
}

function buildFilteredSourceMap(
  sourceMap: Record<string, SourceMetadata>,
  generic: GroundingGenericItem[],
  poi: GroundingPoiItem | null,
  map: GroundingMapItem[],
): Record<string, SourceMetadata> {
  const out: Record<string, SourceMetadata> = {};
  const urls = new Set<string>();

  for (const item of generic) {
    urls.add(item.url);
  }
  if (poi?.url) {
    urls.add(poi.url);
  }
  for (const item of map) {
    if (item.url) {
      urls.add(item.url);
    }
  }

  for (const url of urls) {
    const existing = sourceMap[url];
    const hostname = existing?.hostname || hostnameFromUrl(url);
    out[url] = {
      ...(existing?.title ? { title: existing.title } : {}),
      ...(hostname ? { hostname } : {}),
      age: existing?.age ?? null,
    };
  }

  return out;
}
