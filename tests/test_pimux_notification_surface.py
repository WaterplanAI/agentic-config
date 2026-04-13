#!/usr/bin/env python3
"""Surface checks for pimux notification-mode simplification."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIMUX_PACKAGE_DIR = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux"
PIMUX_INDEX = PIMUX_PACKAGE_DIR / "index.ts"
PIMUX_PATHS = PIMUX_PACKAGE_DIR / "paths.ts"
PIMUX_SCHEMA = PIMUX_PACKAGE_DIR / "schema.ts"
PIMUX_COMMANDS = PROJECT_ROOT / ".pi" / "skills" / "pimux" / "references" / "commands.md"
PIMUX_SKILL = PROJECT_ROOT / ".pi" / "skills" / "pimux" / "SKILL.md"


def test_notification_mode_surface_is_follow_up_only() -> None:
    """pimux should expose only notify-and-follow-up across code and docs."""
    index_text = PIMUX_INDEX.read_text()
    paths_text = PIMUX_PATHS.read_text()
    schema_text = PIMUX_SCHEMA.read_text()
    commands_text = PIMUX_COMMANDS.read_text()
    skill_text = PIMUX_SKILL.read_text()

    assert 'export type NotificationMode = "notify-and-follow-up";' in paths_text
    assert 'export const DEFAULT_NOTIFICATION_MODE: NotificationMode = "notify-and-follow-up";' in paths_text
    assert '--notify|--follow-up|--silent' not in index_text
    assert 'pimux always uses notify-and-follow-up; explicit notification flags are no longer supported.' in index_text
    assert 'notificationMode: Type.Optional' not in schema_text
    assert 'Spawned pimux children always use `notify-and-follow-up`.' in commands_text
    assert 'notification behavior is fixed to `notify-and-follow-up`' in skill_text
