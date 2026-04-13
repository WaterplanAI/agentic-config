import type { AuthStorage } from "@mariozechner/pi-coding-agent";

export const BACKEND_NAMES = ["brave-search", "codex-search", "claude-search"] as const;
export type BackendName = (typeof BACKEND_NAMES)[number];

export const DEFAULT_BACKEND_NAME: BackendName = "brave-search";
export const BRAVE_MONTHLY_LIMIT = 1000;

export type ContextThresholdMode = "strict" | "balanced" | "lenient" | "disabled";

export interface LocationContext {
  lat?: number;
  long?: number;
  city?: string;
  state?: string;
  state_name?: string;
  country?: string;
  postal_code?: string;
}

export interface AppliedWebSearchRequest {
  q: string;
  country?: string;
  search_lang?: string;
  count: number;
  freshness?: string;
  maximum_number_of_urls: number;
  maximum_number_of_tokens: number;
  maximum_number_of_snippets: number;
  maximum_number_of_tokens_per_url: number;
  maximum_number_of_snippets_per_url: number;
  context_threshold_mode: ContextThresholdMode;
  enable_local?: boolean;
  goggles?: string[];
  location?: LocationContext;
}

export interface GroundingGenericItem {
  url: string;
  title: string;
  snippets: string[];
}

export interface GroundingPoiItem {
  name?: string;
  url?: string;
  title?: string;
  snippets?: string[];
}

export interface GroundingMapItem {
  name?: string;
  url?: string;
  title?: string;
  snippets?: string[];
}

export interface SourceMetadata {
  title?: string;
  hostname?: string;
  age?: string[] | null;
}

export interface NormalizedSearchResult {
  grounding: {
    generic: GroundingGenericItem[];
    poi?: GroundingPoiItem | null;
    map?: GroundingMapItem[];
  };
  sources: Record<string, SourceMetadata>;
}

export interface BackendAttempt {
  backend: BackendName;
  status: "skipped" | "error" | "success";
  reason?: string;
}

export interface SourceDetail {
  url: string;
  title?: string;
  hostname?: string;
  age?: string[] | null;
}

export type BraveAuthSource = "env" | "auth.json" | "none";

export interface WebSearchToolDetails {
  query: string;
  request: AppliedWebSearchRequest;
  backend_used: BackendName;
  fallback_chain: BackendAttempt[];
  generic_count: number;
  has_poi: boolean;
  map_count: number;
  sources: SourceDetail[];
  session_cache_hit: boolean;
  brave_auth_source: BraveAuthSource;
}

export interface ToolResultPayload {
  content: Array<{ type: "text"; text: string }>;
  details: WebSearchToolDetails;
  isError?: boolean;
}

export interface LockState {
  locked: boolean;
  pre_lock_active_tools?: string[];
}

export interface BraveUsageState {
  month: string;
  requests_used_this_month: number;
}

export interface SessionStats {
  tool_calls_total: number;
  cache_hits_total: number;
  last_successful_backend?: BackendName;
  backend_attempts: Record<BackendName, number>;
  fallback_errors: Record<BackendName, number>;
}

export interface RuntimeState {
  cache: Map<string, ToolResultPayload>;
  inFlight: Map<string, Promise<ToolResultPayload>>;
  lockState: LockState;
  stats: SessionStats;
  authStorage: AuthStorage;
  braveSetupPromptShown: boolean;
  braveUsage: BraveUsageState;
  braveLane: Promise<void>;
  braveLastStartedAt: number;
  braveUsagePath: string;
  defaultBackend: BackendName;
  backendPreferencePath: string;
}

export function getBackendAttemptOrder(defaultBackend: BackendName): BackendName[] {
  return [defaultBackend, ...BACKEND_NAMES.filter((backend) => backend !== defaultBackend)];
}

export function createEmptyBackendCounter(): Record<BackendName, number> {
  return {
    "brave-search": 0,
    "codex-search": 0,
    "claude-search": 0,
  };
}

export function createEmptyStats(): SessionStats {
  return {
    tool_calls_total: 0,
    cache_hits_total: 0,
    backend_attempts: createEmptyBackendCounter(),
    fallback_errors: createEmptyBackendCounter(),
  };
}

export function currentMonthKey(now = new Date()): string {
  return now.toISOString().slice(0, 7);
}
