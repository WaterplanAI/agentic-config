import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

/**
 * Project-local pimux compatibility shim.
 *
 * The authoritative repo-owned pimux runtime now lives under:
 * `packages/pi-ac-workflow/extensions/pimux/`
 *
 * The previous project-local implementation has been archived at:
 * `.pi/archive/extensions/pimux-local-runtime/`
 *
 * Keep this shim tool-free so managed child launches that still pass
 * `-e .pi/extensions/pimux/index.ts` do not conflict with the package-owned
 * pimux runtime auto-loaded from the workflow package.
 */
export default function pimuxCompatibilityShim(_pi: ExtensionAPI): void {
	// Intentionally empty.
}
