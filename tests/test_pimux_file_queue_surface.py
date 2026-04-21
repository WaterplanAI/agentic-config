#!/usr/bin/env python3
"""Surface checks for pimux file-queue based state serialization."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIMUX_PACKAGE_DIR = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux"
FILE_QUEUE = PIMUX_PACKAGE_DIR / "file-queue.ts"
REGISTRY_RUNTIME = PIMUX_PACKAGE_DIR / "registry.ts"
BRIDGE_RUNTIME = PIMUX_PACKAGE_DIR / "bridge.ts"


def test_file_queue_helper_exists_for_serialized_state_mutations() -> None:
    """The extension should define a shared per-file queue helper for concurrent mutations."""
    text = FILE_QUEUE.read_text()
    assert "const fileOperationQueues = new Map<string, Promise<void>>();" in text
    assert "export async function withQueuedFileOperation" in text



def test_registry_updates_use_file_queue_serialization() -> None:
    """Registry and session-registry writes should be serialized through the queue helper."""
    text = REGISTRY_RUNTIME.read_text()
    assert 'import { withQueuedFileOperation } from "./file-queue.ts";' in text
    assert "return await withQueuedFileOperation(registryPath, async () => {" in text
    assert "await withQueuedFileOperation(sessionRegistryPath, async () => {" in text
    assert "await withQueuedFileOperation(manifestPath, async () => {" in text



def test_bridge_state_and_events_use_file_queue_serialization() -> None:
    """Bridge state writes and event appends should be serialized through the queue helper."""
    text = BRIDGE_RUNTIME.read_text()
    assert 'import { withQueuedFileOperation } from "./file-queue.ts";' in text
    assert "await withQueuedFileOperation(parentStatePath, async () => {" in text
    assert "await withQueuedFileOperation(childStatePath, async () => {" in text
    assert "await withQueuedFileOperation(eventsPath, async () => {" in text
    assert "return await withQueuedFileOperation(childStatePath, async () => {" in text
