import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { BACKEND_NAMES, DEFAULT_BACKEND_NAME } from "./types.js";
import type { BackendName } from "./types.js";

interface BackendPreferenceFile {
  default_backend?: unknown;
}

export async function loadDefaultBackend(path: string): Promise<BackendName> {
  try {
    const raw = await readFile(path, "utf8");
    const parsed = JSON.parse(raw) as BackendPreferenceFile;
    return normalizeBackendName(parsed.default_backend) ?? DEFAULT_BACKEND_NAME;
  } catch {
    return DEFAULT_BACKEND_NAME;
  }
}

export async function saveDefaultBackend(path: string, backend: BackendName): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify({ default_backend: backend }, null, 2)}\n`, "utf8");
}

function normalizeBackendName(value: unknown): BackendName | undefined {
  if (typeof value !== "string") {
    return undefined;
  }

  const candidate = value.trim().toLowerCase();
  return BACKEND_NAMES.includes(candidate as BackendName) ? (candidate as BackendName) : undefined;
}
