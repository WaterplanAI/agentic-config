const INSTALL_STATE_KEY = Symbol.for("@agentic-config/pi-compat.install-state");

function assertRuntime(runtime) {
  if (!runtime || (typeof runtime !== "object" && typeof runtime !== "function")) {
    throw new TypeError("pi-compat install guard requires a runtime object.");
  }
}

function getInstallState(runtime) {
  assertRuntime(runtime);

  if (!Object.prototype.hasOwnProperty.call(runtime, INSTALL_STATE_KEY)) {
    Object.defineProperty(runtime, INSTALL_STATE_KEY, {
      value: {
        extensions: new Set(),
      },
      enumerable: false,
      configurable: true,
      writable: false,
    });
  }

  return runtime[INSTALL_STATE_KEY];
}

export function markPiCompatExtensionInstalled(runtime, extensionId) {
  if (typeof extensionId !== "string" || extensionId.trim() === "") {
    throw new TypeError("pi-compat install guard requires a non-empty extensionId.");
  }

  const state = getInstallState(runtime);
  const normalizedId = extensionId.trim();

  if (state.extensions.has(normalizedId)) {
    return false;
  }

  state.extensions.add(normalizedId);
  return true;
}

export function listPiCompatInstalledExtensions(runtime) {
  return [...getInstallState(runtime).extensions].sort();
}

export function resetPiCompatInstallStateForTests(runtime) {
  if (!runtime || (typeof runtime !== "object" && typeof runtime !== "function")) {
    return;
  }

  if (!Object.prototype.hasOwnProperty.call(runtime, INSTALL_STATE_KEY)) {
    return;
  }

  runtime[INSTALL_STATE_KEY].extensions.clear();
}
