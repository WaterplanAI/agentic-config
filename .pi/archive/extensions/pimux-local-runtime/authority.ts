export interface BridgeAuthorityBinding {
	authoritativeSessionKey?: string;
	authoritativeSessionFile?: string;
	authoritativeLeafId?: string;
	authoritativeProcessId?: number;
}

export interface BridgeRuntimeSessionIdentity {
	sessionKey: string;
	sessionFile?: string;
	leafId?: string;
	processId: number;
}

export interface BridgeAuthorityEvaluation {
	isAuthoritative: boolean;
	reason?: string;
}

export function hasBoundBridgeAuthority(binding: BridgeAuthorityBinding): boolean {
	return Boolean(
		binding.authoritativeSessionKey ||
			binding.authoritativeSessionFile ||
			binding.authoritativeLeafId ||
			binding.authoritativeProcessId !== undefined,
	);
}

export function bindBridgeAuthoritativeSession(current: BridgeRuntimeSessionIdentity): BridgeAuthorityBinding {
	return {
		authoritativeSessionKey: current.sessionKey,
		authoritativeSessionFile: current.sessionFile,
		authoritativeLeafId: current.leafId,
		authoritativeProcessId: current.processId,
	};
}

function mismatchReason(label: string, expected: string | number, actual: string | number | undefined): string {
	return `Bridge is bound to ${label} ${String(expected)}, current ${label} is ${actual === undefined ? "missing" : String(actual)}.`;
}

export function evaluateBridgeAuthority(
	binding: BridgeAuthorityBinding,
	current: BridgeRuntimeSessionIdentity,
): BridgeAuthorityEvaluation {
	if (!hasBoundBridgeAuthority(binding)) {
		return {
			isAuthoritative: false,
			reason: "No authoritative pimux child session has been bound to this bridge yet.",
		};
	}

	if (binding.authoritativeSessionFile) {
		if (current.sessionFile !== binding.authoritativeSessionFile) {
			return {
				isAuthoritative: false,
				reason: mismatchReason("session file", binding.authoritativeSessionFile, current.sessionFile),
			};
		}
		return { isAuthoritative: true };
	}

	if (binding.authoritativeSessionKey) {
		if (current.sessionKey !== binding.authoritativeSessionKey) {
			return {
				isAuthoritative: false,
				reason: mismatchReason("session key", binding.authoritativeSessionKey, current.sessionKey),
			};
		}
		if (binding.authoritativeProcessId !== undefined && current.processId !== binding.authoritativeProcessId) {
			return {
				isAuthoritative: false,
				reason: mismatchReason("process id", binding.authoritativeProcessId, current.processId),
			};
		}
		if (binding.authoritativeProcessId !== undefined) {
			return { isAuthoritative: true };
		}
		if (binding.authoritativeLeafId && current.leafId !== binding.authoritativeLeafId) {
			return {
				isAuthoritative: false,
				reason: mismatchReason("leaf", binding.authoritativeLeafId, current.leafId),
			};
		}
		return { isAuthoritative: true };
	}

	if (binding.authoritativeLeafId && current.leafId !== binding.authoritativeLeafId) {
		return {
			isAuthoritative: false,
			reason: mismatchReason("leaf", binding.authoritativeLeafId, current.leafId),
		};
	}

	if (binding.authoritativeProcessId !== undefined && current.processId !== binding.authoritativeProcessId) {
		return {
			isAuthoritative: false,
			reason: mismatchReason("process id", binding.authoritativeProcessId, current.processId),
		};
	}

	return { isAuthoritative: true };
}
