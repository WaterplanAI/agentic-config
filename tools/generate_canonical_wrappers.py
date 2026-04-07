#!/usr/bin/env python3
"""Render seeded canonical skill/package inputs into Claude and pi outputs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Iterable, Sequence

import yaml  # type: ignore[import-untyped]


class GeneratorError(RuntimeError):
    """Raised when canonical inputs are invalid or generation cannot proceed."""


@dataclass(frozen=True)
class AssetMapping:
    asset_id: str
    source: str
    outputs: dict[str, str]


@dataclass(frozen=True)
class BodyOverrides:
    prepend: tuple[str, ...]
    append: tuple[str, ...]


@dataclass(frozen=True)
class RenderConfig:
    harness: str
    status: str
    output_path: str
    display_name: str
    allowed_tools: tuple[str, ...]
    frontmatter_enabled: bool
    body_file: str | None
    placeholder_values: dict[str, str]
    body_overrides: BodyOverrides
    frontmatter_extra: dict[str, Any]
    description: str | None = None


@dataclass(frozen=True)
class HookSpec:
    hook_id: str
    script_path: str
    timeout_ms: int
    failure_mode: str


@dataclass(frozen=True)
class HookGroup:
    matcher: str
    hooks: tuple[HookSpec, ...]


@dataclass(frozen=True)
class RuntimeAttachment:
    attachment_id: str
    harness: str
    kind: str
    output_path: str
    package_entry: str
    plugin_root_mode: str
    dependency_refs: tuple[str, ...]
    ask_fallback: dict[str, str]
    hook_groups: tuple[HookGroup, ...]


@dataclass(frozen=True)
class PiDependencyConfig:
    package_dependencies: tuple[str, ...]
    bundled_dependencies: tuple[str, ...]
    extension_exports: tuple[str, ...]


@dataclass(frozen=True)
class SkillConfig:
    package_root: Path
    skill_root: Path
    skill_id: str
    kind: str
    summary: str
    project_agnostic: bool
    body_file: str
    assets: tuple[AssetMapping, ...]
    attachment_refs: tuple[str, ...]
    renders: dict[str, RenderConfig]


@dataclass(frozen=True)
class PackageConfig:
    package_root: Path
    plugin_id: str
    claude_plugin_path: str
    pi_package: str
    pi_package_path: str
    shared_assets: tuple[AssetMapping, ...]
    placeholder_values: dict[str, dict[str, str]]
    runtime_attachments: tuple[RuntimeAttachment, ...]
    pi_dependencies: PiDependencyConfig
    skills: tuple[SkillConfig, ...]


@dataclass(frozen=True)
class PlannedWrite:
    path: Path
    content: bytes


DEFAULT_PLACEHOLDERS: Final[dict[str, dict[str, str]]] = {
    "PACKAGE_ASSETS": {"claude": "${CLAUDE_PLUGIN_ROOT}", "pi": "../../assets"},
    "SKILL_ASSETS": {"claude": ".", "pi": "."},
    "SPEC_ROOT": {"claude": "specs", "pi": ".specs/specs"},
}
SUPPORTED_HARNESSES: Final[tuple[str, str]] = ("claude", "pi")
SUPPORTED_RENDER_STATUSES: Final[set[str]] = {"supported", "partial", "deferred"}
RESERVED_FRONTMATTER_KEYS: Final[set[str]] = {"name", "description", "project-agnostic", "allowed-tools"}


def main(argv: Sequence[str]) -> int:
    """Run the generator CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report drift without writing files.",
    )
    parser.add_argument(
        "--plugin",
        action="append",
        default=[],
        help="Limit generation to one or more canonical plugin ids.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    try:
        packages = load_canonical_packages(repo_root, set(args.plugin))
        planned_writes = plan_generation(repo_root, packages)
    except GeneratorError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.check:
        drift_paths = [str(path.relative_to(repo_root)) for path in detect_drift(planned_writes)]
        if drift_paths:
            print("Canonical output drift detected:")
            for drift_path in drift_paths:
                print(f"- {drift_path}")
            return 1
        print("Canonical outputs are up to date.")
        return 0

    written_paths = apply_writes(planned_writes)
    if written_paths:
        print("Updated canonical outputs:")
        for path in written_paths:
            print(f"- {path.relative_to(repo_root)}")
    else:
        print("Canonical outputs are already up to date.")
    return 0


def load_canonical_packages(repo_root: Path, selected_plugins: set[str]) -> tuple[PackageConfig, ...]:
    """Load canonical package configurations from disk."""
    canonical_root = repo_root / "canonical"
    if not canonical_root.exists():
        raise GeneratorError(f"missing canonical root: {canonical_root}")

    package_paths = sorted(path for path in canonical_root.iterdir() if path.is_dir())
    packages = tuple(load_package_config(path) for path in package_paths)
    if not selected_plugins:
        return packages

    filtered_packages = tuple(package for package in packages if package.plugin_id in selected_plugins)
    missing_plugins = sorted(selected_plugins - {package.plugin_id for package in filtered_packages})
    if missing_plugins:
        raise GeneratorError(f"unknown canonical plugin ids: {', '.join(missing_plugins)}")
    return filtered_packages


def load_package_config(package_root: Path) -> PackageConfig:
    """Load one canonical package and its child skills."""
    package_yaml = read_yaml_mapping(package_root / "package.yaml")
    plugin_id = require_str(package_yaml, "plugin_id", package_root / "package.yaml")
    shared_assets = parse_asset_mappings(package_yaml.get("shared_assets", []), package_root / "package.yaml", "shared_assets")
    placeholder_values = parse_placeholder_values(
        package_yaml.get("placeholder_values", {}),
        package_root / "package.yaml",
    )
    runtime_attachments = parse_runtime_attachments(
        package_yaml.get("runtime_attachments", []),
        package_root / "package.yaml",
    )
    pi_dependencies = parse_pi_dependencies(package_yaml.get("dependencies", {}), package_root / "package.yaml")

    skills_root = package_root / "skills"
    skill_paths = sorted(path for path in skills_root.iterdir() if path.is_dir()) if skills_root.exists() else []
    skills = tuple(load_skill_config(package_root, skill_path) for skill_path in skill_paths)
    return PackageConfig(
        package_root=package_root,
        plugin_id=plugin_id,
        claude_plugin_path=require_str(package_yaml, "claude_plugin_path", package_root / "package.yaml"),
        pi_package=require_str(package_yaml, "pi_package", package_root / "package.yaml"),
        pi_package_path=require_str(package_yaml, "pi_package_path", package_root / "package.yaml"),
        shared_assets=shared_assets,
        placeholder_values=placeholder_values,
        runtime_attachments=runtime_attachments,
        pi_dependencies=pi_dependencies,
        skills=skills,
    )


def load_skill_config(package_root: Path, skill_root: Path) -> SkillConfig:
    """Load one canonical skill."""
    skill_yaml = read_yaml_mapping(skill_root / "skill.yaml")
    renders_raw = require_mapping(skill_yaml, "renders", skill_root / "skill.yaml")
    renders: dict[str, RenderConfig] = {}
    for harness in SUPPORTED_HARNESSES:
        if harness not in renders_raw:
            raise GeneratorError(f"{skill_root / 'skill.yaml'} is missing renders.{harness}")
        renders[harness] = parse_render_config(harness, renders_raw[harness], skill_root / "skill.yaml")

    return SkillConfig(
        package_root=package_root,
        skill_root=skill_root,
        skill_id=require_str(skill_yaml, "skill_id", skill_root / "skill.yaml"),
        kind=require_str(skill_yaml, "kind", skill_root / "skill.yaml"),
        summary=require_str(skill_yaml, "summary", skill_root / "skill.yaml"),
        project_agnostic=require_bool(skill_yaml, "project_agnostic", skill_root / "skill.yaml"),
        body_file=require_str(skill_yaml, "body_file", skill_root / "skill.yaml"),
        assets=parse_asset_mappings(skill_yaml.get("assets", []), skill_root / "skill.yaml", "assets"),
        attachment_refs=tuple(parse_string_list(skill_yaml.get("attachment_refs", []), skill_root / "skill.yaml", "attachment_refs")),
        renders=renders,
    )


def read_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read a YAML file and require a top-level mapping."""
    if not path.exists():
        raise GeneratorError(f"missing YAML file: {path}")
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:  # pragma: no cover - exercised by runtime failures only
        raise GeneratorError(f"failed to parse YAML at {path}: {error}") from error
    if not isinstance(data, dict):
        raise GeneratorError(f"expected top-level mapping in {path}")
    return data


def parse_asset_mappings(raw_value: Any, path: Path, field_name: str) -> tuple[AssetMapping, ...]:
    """Parse asset mapping lists."""
    items = parse_list(raw_value, path, field_name)
    mappings: list[AssetMapping] = []
    for index, item in enumerate(items):
        item_path = f"{field_name}[{index}]"
        item_mapping = require_inline_mapping(item, path, item_path)
        outputs_mapping = require_inline_mapping(item_mapping.get("outputs", {}), path, f"{item_path}.outputs")
        outputs: dict[str, str] = {}
        for harness, value in outputs_mapping.items():
            outputs[str(harness)] = require_inline_str(value, path, f"{item_path}.outputs.{harness}")
        mappings.append(
            AssetMapping(
                asset_id=require_inline_str(item_mapping.get("asset_id"), path, f"{item_path}.asset_id"),
                source=require_inline_str(item_mapping.get("source"), path, f"{item_path}.source"),
                outputs=outputs,
            )
        )
    return tuple(mappings)


def parse_placeholder_values(raw_value: Any, path: Path) -> dict[str, dict[str, str]]:
    """Parse placeholder values keyed by placeholder then harness."""
    placeholder_mapping = require_inline_mapping(raw_value, path, "placeholder_values")
    parsed: dict[str, dict[str, str]] = {}
    for placeholder_name, harness_mapping in placeholder_mapping.items():
        harness_values_raw = require_inline_mapping(harness_mapping, path, f"placeholder_values.{placeholder_name}")
        parsed[str(placeholder_name)] = {
            str(harness): require_inline_str(value, path, f"placeholder_values.{placeholder_name}.{harness}")
            for harness, value in harness_values_raw.items()
        }
    return parsed


def parse_runtime_attachments(raw_value: Any, path: Path) -> tuple[RuntimeAttachment, ...]:
    """Parse runtime-attachment declarations."""
    items = parse_list(raw_value, path, "runtime_attachments")
    attachments: list[RuntimeAttachment] = []
    for index, item in enumerate(items):
        item_path = f"runtime_attachments[{index}]"
        mapping = require_inline_mapping(item, path, item_path)
        hooks = parse_hook_groups(mapping.get("hooks", []), path, f"{item_path}.hooks")
        attachments.append(
            RuntimeAttachment(
                attachment_id=require_inline_str(mapping.get("attachment_id"), path, f"{item_path}.attachment_id"),
                harness=require_inline_str(mapping.get("harness"), path, f"{item_path}.harness"),
                kind=require_inline_str(mapping.get("kind"), path, f"{item_path}.kind"),
                output_path=require_inline_str(mapping.get("output_path"), path, f"{item_path}.output_path"),
                package_entry=require_inline_str(mapping.get("package_entry"), path, f"{item_path}.package_entry"),
                plugin_root_mode=require_inline_str(mapping.get("plugin_root_mode"), path, f"{item_path}.plugin_root_mode"),
                dependency_refs=tuple(parse_string_list(mapping.get("dependency_refs", []), path, f"{item_path}.dependency_refs")),
                ask_fallback=parse_string_mapping(mapping.get("ask_fallback", {}), path, f"{item_path}.ask_fallback"),
                hook_groups=hooks,
            )
        )
    return tuple(attachments)


def parse_hook_groups(raw_value: Any, path: Path, field_name: str) -> tuple[HookGroup, ...]:
    """Parse hook matcher groups."""
    items = parse_list(raw_value, path, field_name)
    groups: list[HookGroup] = []
    for index, item in enumerate(items):
        item_path = f"{field_name}[{index}]"
        mapping = require_inline_mapping(item, path, item_path)
        hooks: list[HookSpec] = []
        for hook_index, hook_item in enumerate(parse_list(mapping.get("hooks", []), path, f"{item_path}.hooks")):
            hook_path = f"{item_path}.hooks[{hook_index}]"
            hook_mapping = require_inline_mapping(hook_item, path, hook_path)
            hooks.append(
                HookSpec(
                    hook_id=require_inline_str(hook_mapping.get("id"), path, f"{hook_path}.id"),
                    script_path=require_inline_str(hook_mapping.get("script_path"), path, f"{hook_path}.script_path"),
                    timeout_ms=require_inline_int(hook_mapping.get("timeout_ms"), path, f"{hook_path}.timeout_ms"),
                    failure_mode=require_inline_str(hook_mapping.get("failure_mode"), path, f"{hook_path}.failure_mode"),
                )
            )
        groups.append(
            HookGroup(
                matcher=require_inline_str(mapping.get("matcher"), path, f"{item_path}.matcher"),
                hooks=tuple(hooks),
            )
        )
    return tuple(groups)


def parse_pi_dependencies(raw_value: Any, path: Path) -> PiDependencyConfig:
    """Parse optional pi dependency metadata."""
    dependencies_mapping = require_inline_mapping(raw_value, path, "dependencies")
    pi_mapping = require_inline_mapping(dependencies_mapping.get("pi", {}), path, "dependencies.pi")
    return PiDependencyConfig(
        package_dependencies=tuple(parse_string_list(pi_mapping.get("package_dependencies", []), path, "dependencies.pi.package_dependencies")),
        bundled_dependencies=tuple(parse_string_list(pi_mapping.get("bundled_dependencies", []), path, "dependencies.pi.bundled_dependencies")),
        extension_exports=tuple(parse_string_list(pi_mapping.get("extension_exports", []), path, "dependencies.pi.extension_exports")),
    )


def parse_render_config(harness: str, raw_value: Any, path: Path) -> RenderConfig:
    """Parse one harness render block."""
    mapping = require_inline_mapping(raw_value, path, f"renders.{harness}")
    status = require_inline_str(mapping.get("status"), path, f"renders.{harness}.status")
    if status not in SUPPORTED_RENDER_STATUSES:
        raise GeneratorError(f"{path} has unsupported renders.{harness}.status value: {status}")
    body_overrides_mapping = require_inline_mapping(mapping.get("body_overrides", {}), path, f"renders.{harness}.body_overrides")
    frontmatter_extra = parse_yaml_mapping(mapping.get("frontmatter_extra", {}), path, f"renders.{harness}.frontmatter_extra")
    conflicting_frontmatter_keys = sorted(RESERVED_FRONTMATTER_KEYS & set(frontmatter_extra))
    if conflicting_frontmatter_keys:
        joined_keys = ", ".join(conflicting_frontmatter_keys)
        raise GeneratorError(f"{path} uses reserved frontmatter_extra keys for renders.{harness}: {joined_keys}")
    return RenderConfig(
        harness=harness,
        status=status,
        output_path=require_inline_str(mapping.get("output_path"), path, f"renders.{harness}.output_path"),
        display_name=require_inline_str(mapping.get("display_name"), path, f"renders.{harness}.display_name"),
        allowed_tools=tuple(parse_string_list(mapping.get("allowed_tools", []), path, f"renders.{harness}.allowed_tools")),
        frontmatter_enabled=require_inline_bool(mapping.get("frontmatter_enabled", True), path, f"renders.{harness}.frontmatter_enabled"),
        body_file=require_optional_inline_str(mapping.get("body_file"), path, f"renders.{harness}.body_file"),
        placeholder_values=parse_string_mapping(mapping.get("placeholder_values", {}), path, f"renders.{harness}.placeholder_values"),
        body_overrides=BodyOverrides(
            prepend=tuple(parse_string_list(body_overrides_mapping.get("prepend", []), path, f"renders.{harness}.body_overrides.prepend")),
            append=tuple(parse_string_list(body_overrides_mapping.get("append", []), path, f"renders.{harness}.body_overrides.append")),
        ),
        frontmatter_extra=frontmatter_extra,
        description=require_optional_inline_str(mapping.get("description"), path, f"renders.{harness}.description"),
    )


def plan_generation(repo_root: Path, packages: Iterable[PackageConfig]) -> tuple[PlannedWrite, ...]:
    """Plan all file writes required for the selected canonical packages."""
    planned_writes: dict[Path, bytes] = {}
    version = (repo_root / "VERSION").read_text().strip()
    for package in packages:
        plan_package_assets(repo_root, package, planned_writes)
        plan_runtime_attachments(repo_root, package, planned_writes)
        plan_package_manifest(repo_root, package, planned_writes, version)
        for skill in package.skills:
            plan_skill_outputs(repo_root, package, skill, planned_writes)
            plan_skill_assets(repo_root, package, skill, planned_writes)
    return tuple(PlannedWrite(path=path, content=content) for path, content in sorted(planned_writes.items()))


def plan_package_assets(repo_root: Path, package: PackageConfig, planned_writes: dict[Path, bytes]) -> None:
    """Plan package-shared asset copies."""
    for asset_mapping in package.shared_assets:
        source_root = package.package_root / asset_mapping.source
        if not source_root.exists():
            raise GeneratorError(f"missing package asset source: {source_root}")
        for harness, relative_destination in asset_mapping.outputs.items():
            destination_root = harness_root(repo_root, package, harness) / relative_destination
            replacements = build_placeholder_replacements(package, harness)
            queue_tree_copy(source_root, destination_root, planned_writes, replacements)


def plan_runtime_attachments(repo_root: Path, package: PackageConfig, planned_writes: dict[Path, bytes]) -> None:
    """Plan package-local runtime-attachment outputs."""
    hook_compat_attachments = [
        attachment
        for attachment in package.runtime_attachments
        if attachment.harness == "pi" and attachment.kind == "hook-compat"
    ]
    if len(hook_compat_attachments) > 1:
        raise GeneratorError(f"{package.package_root / 'package.yaml'} declares more than one pi hook-compat attachment")
    if not hook_compat_attachments:
        return

    attachment = hook_compat_attachments[0]
    if attachment.plugin_root_mode != "package-assets":
        raise GeneratorError(f"unsupported plugin_root_mode for {package.plugin_id}: {attachment.plugin_root_mode}")
    destination_path = harness_root(repo_root, package, "pi") / attachment.output_path
    queue_text_write(destination_path, render_hook_compat_extension(package, attachment), planned_writes)


def plan_package_manifest(
    repo_root: Path,
    package: PackageConfig,
    planned_writes: dict[Path, bytes],
    version: str,
) -> None:
    """Plan package.json synchronization for generator-owned fields."""
    package_json_path = harness_root(repo_root, package, "pi") / "package.json"
    if not package_json_path.exists():
        raise GeneratorError(f"missing package.json for {package.plugin_id}: {package_json_path}")

    package_json = json.loads(package_json_path.read_text())
    if package_json.get("name") != package.pi_package:
        raise GeneratorError(
            f"package.json name mismatch for {package.plugin_id}: {package_json.get('name')} != {package.pi_package}"
        )

    pi_block = package_json.setdefault("pi", {})
    if not isinstance(pi_block, dict):
        raise GeneratorError(f"invalid pi block in {package_json_path}")
    pi_block["skills"] = merge_required_items(as_string_list(pi_block.get("skills", []), package_json_path, "pi.skills"), ["./skills"])

    required_extensions = ["./extensions"]
    required_extensions.extend(package.pi_dependencies.extension_exports)
    pi_block["extensions"] = merge_required_items(
        as_string_list(pi_block.get("extensions", []), package_json_path, "pi.extensions"),
        required_extensions,
    )

    dependency_names = merge_required_items(
        list(package.pi_dependencies.package_dependencies),
        [dependency for attachment in package.runtime_attachments for dependency in attachment.dependency_refs],
    )
    if dependency_names:
        dependencies_block = package_json.setdefault("dependencies", {})
        if not isinstance(dependencies_block, dict):
            raise GeneratorError(f"invalid dependencies block in {package_json_path}")
        for dependency_name in dependency_names:
            dependencies_block[dependency_name] = version

    bundled_dependencies = merge_required_items(
        as_string_list(package_json.get("bundledDependencies", []), package_json_path, "bundledDependencies"),
        list(package.pi_dependencies.bundled_dependencies),
    )
    if bundled_dependencies:
        package_json["bundledDependencies"] = bundled_dependencies

    queue_text_write(package_json_path, json.dumps(package_json, indent=2) + "\n", planned_writes)


def plan_skill_outputs(
    repo_root: Path,
    package: PackageConfig,
    skill: SkillConfig,
    planned_writes: dict[Path, bytes],
) -> None:
    """Plan skill markdown outputs for supported or partial renders."""
    for harness, render in skill.renders.items():
        if render.status == "deferred":
            continue
        body_template_path = skill.skill_root / (render.body_file or skill.body_file)
        if not body_template_path.exists():
            raise GeneratorError(f"missing body file for {skill.skill_id}/{harness}: {body_template_path}")
        body_template = body_template_path.read_text()
        destination_path = harness_root(repo_root, package, harness) / render.output_path
        markdown = render_skill_markdown(package, skill, render, body_template)
        queue_text_write(destination_path, markdown, planned_writes)


def plan_skill_assets(
    repo_root: Path,
    package: PackageConfig,
    skill: SkillConfig,
    planned_writes: dict[Path, bytes],
) -> None:
    """Plan skill-local copied support trees."""
    for asset_mapping in skill.assets:
        source_root = skill.skill_root / asset_mapping.source
        if not source_root.exists():
            raise GeneratorError(f"missing skill asset source: {source_root}")
        for harness, relative_destination in asset_mapping.outputs.items():
            render = skill.renders.get(harness)
            if render is None or render.status == "deferred":
                continue
            skill_output_root = (harness_root(repo_root, package, harness) / render.output_path).parent
            destination_root = skill_output_root / relative_destination
            replacements = build_placeholder_replacements(package, harness, render.placeholder_values)
            queue_tree_copy(source_root, destination_root, planned_writes, replacements)


def render_skill_markdown(
    package: PackageConfig,
    skill: SkillConfig,
    render: RenderConfig,
    body_template: str,
) -> str:
    """Render one skill markdown file."""
    replacements = build_placeholder_replacements(package, render.harness, render.placeholder_values)
    rendered_body = apply_known_placeholders(body_template, replacements)
    prepend_blocks = tuple(apply_known_placeholders(block, replacements) for block in render.body_overrides.prepend)
    append_blocks = tuple(apply_known_placeholders(block, replacements) for block in render.body_overrides.append)
    body_parts = [block for block in (*prepend_blocks, rendered_body, *append_blocks) if block.strip()]
    markdown_body = "\n\n".join(part.rstrip() for part in body_parts).strip()
    markdown_body += "\n"
    if not render.frontmatter_enabled:
        return markdown_body

    frontmatter_lines = [
        "---",
        f"name: {render.display_name}",
        f"description: {json.dumps(render.description or skill.summary)}",
        f"project-agnostic: {'true' if skill.project_agnostic else 'false'}",
    ]
    if render.allowed_tools:
        frontmatter_lines.append("allowed-tools:")
        frontmatter_lines.extend(f"  - {tool}" for tool in render.allowed_tools)
    frontmatter_lines.extend(render_extra_frontmatter(render.frontmatter_extra, replacements))
    frontmatter_lines.append("---")
    return "\n".join(frontmatter_lines) + "\n\n" + markdown_body


def build_placeholder_replacements(
    package: PackageConfig,
    harness: str,
    extra_placeholder_values: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build placeholder replacements for one harness render."""
    replacements: dict[str, str] = {}
    for placeholder_name, values_by_harness in DEFAULT_PLACEHOLDERS.items():
        if harness in values_by_harness:
            replacements[placeholder_name] = values_by_harness[harness].rstrip("\n")
    for placeholder_name, values_by_harness in package.placeholder_values.items():
        if harness in values_by_harness:
            replacements[placeholder_name] = values_by_harness[harness].rstrip("\n")
    if extra_placeholder_values:
        replacements.update({key: value.rstrip("\n") for key, value in extra_placeholder_values.items()})
    return replacements


def apply_known_placeholders(text: str, replacements: dict[str, str]) -> str:
    """Replace only the known placeholder keys, leaving unrelated template markers intact."""
    rendered = text
    for _ in range(len(replacements) + 1):
        previous = rendered
        for placeholder_name, value in replacements.items():
            rendered = rendered.replace(f"{{{{{placeholder_name}}}}}", value)
        if rendered == previous:
            break
    return rendered


def apply_known_placeholders_to_yaml_value(value: Any, replacements: dict[str, str]) -> Any:
    """Recursively replace known placeholders inside YAML-compatible data."""
    if isinstance(value, str):
        return apply_known_placeholders(value, replacements)
    if isinstance(value, list):
        return [apply_known_placeholders_to_yaml_value(item, replacements) for item in value]
    if isinstance(value, dict):
        return {
            str(key): apply_known_placeholders_to_yaml_value(item, replacements)
            for key, item in value.items()
        }
    return value


def render_extra_frontmatter(frontmatter_extra: dict[str, Any], replacements: dict[str, str]) -> list[str]:
    """Render any additional frontmatter fields after placeholder substitution."""
    if not frontmatter_extra:
        return []
    rendered_extra = apply_known_placeholders_to_yaml_value(frontmatter_extra, replacements)
    extra_yaml = yaml.safe_dump(rendered_extra, sort_keys=False, default_flow_style=False).strip()
    if not extra_yaml:
        return []
    return extra_yaml.splitlines()


def render_hook_compat_extension(package: PackageConfig, attachment: RuntimeAttachment) -> str:
    """Render the package-local hook-compat registration module."""
    function_name = f"register{pascal_case(package.plugin_id)}HookCompat"
    lines = [
        'import { dirname, resolve } from "node:path";',
        'import { fileURLToPath } from "node:url";',
        "",
        'const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");',
        'const ASSET_ROOT = resolve(PACKAGE_ROOT, "assets");',
        "",
        'const { registerHookCompatPackage } = await loadHookCompatModule();',
        "",
        'async function loadHookCompatModule() {',
        '  try {',
        '    return await import("@agentic-config/pi-compat/extensions/hook-compat");',
        '  } catch (error) {',
        '    if (error && typeof error === "object" && "code" in error && error.code !== "ERR_MODULE_NOT_FOUND") {',
        '      throw error;',
        '    }',
        '    return await import(new URL("../../pi-compat/extensions/hook-compat/index.js", import.meta.url).href);',
        '  }',
        '}',
        "",
        f"export default function {function_name}(pi) {{",
        '  registerHookCompatPackage(pi, {',
        f'    packageId: "{package.pi_package}",',
        '    pluginRoot: ASSET_ROOT,',
    ]
    if attachment.ask_fallback:
        lines.append('    askFallback: {')
        for key, value in attachment.ask_fallback.items():
            lines.append(f'      {key}: "{value}",')
        lines.append('    },')
    lines.append('    hooks: [')
    for group in attachment.hook_groups:
        lines.append('      {')
        lines.append(f'        matcher: "{group.matcher}",')
        lines.append('        hooks: [')
        for hook in group.hooks:
            lines.append('          {')
            lines.append(f'            id: "{hook.hook_id}",')
            lines.append(f'            scriptPath: "{hook.script_path}",')
            lines.append(f'            timeoutMs: {hook.timeout_ms},')
            lines.append(f'            failureMode: "{hook.failure_mode}",')
            lines.append('          },')
        lines.append('        ],')
        lines.append('      },')
    lines.append('    ],')
    lines.append('  });')
    lines.append('}')
    return "\n".join(lines) + "\n"


def harness_root(repo_root: Path, package: PackageConfig, harness: str) -> Path:
    """Resolve the root output directory for one harness."""
    if harness == "claude":
        return repo_root / package.claude_plugin_path
    if harness == "pi":
        return repo_root / package.pi_package_path
    raise GeneratorError(f"unsupported harness: {harness}")


def queue_tree_copy(
    source_root: Path,
    destination_root: Path,
    planned_writes: dict[Path, bytes],
    replacements: dict[str, str],
) -> None:
    """Queue copies for all files under one tree without deleting siblings."""
    for source_path in sorted(path for path in source_root.rglob("*") if path.is_file()):
        relative_path = source_path.relative_to(source_root)
        queue_binary_write(
            destination_root / relative_path,
            render_copied_asset(source_path.read_bytes(), replacements),
            planned_writes,
        )


def queue_text_write(path: Path, content: str, planned_writes: dict[Path, bytes]) -> None:
    """Queue one UTF-8 text file write."""
    queue_binary_write(path, content.encode("utf-8"), planned_writes)


def render_copied_asset(content: bytes, replacements: dict[str, str]) -> bytes:
    """Render known placeholders inside copied UTF-8 text assets only."""
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    rendered = apply_known_placeholders(decoded, replacements)
    return rendered.encode("utf-8")


def queue_binary_write(path: Path, content: bytes, planned_writes: dict[Path, bytes]) -> None:
    """Queue one file write and reject conflicting duplicate plans."""
    existing = planned_writes.get(path)
    if existing is not None and existing != content:
        raise GeneratorError(f"conflicting planned writes for {path}")
    planned_writes[path] = content


def detect_drift(planned_writes: Iterable[PlannedWrite]) -> tuple[Path, ...]:
    """Return the paths that would change under the current generation plan."""
    drift_paths: list[Path] = []
    for planned_write in planned_writes:
        existing_content = planned_write.path.read_bytes() if planned_write.path.exists() else None
        if existing_content != planned_write.content:
            drift_paths.append(planned_write.path)
    return tuple(drift_paths)


def apply_writes(planned_writes: Iterable[PlannedWrite]) -> tuple[Path, ...]:
    """Write changed files and return the paths that changed."""
    changed_paths: list[Path] = []
    for planned_write in planned_writes:
        existing_content = planned_write.path.read_bytes() if planned_write.path.exists() else None
        if existing_content == planned_write.content:
            continue
        planned_write.path.parent.mkdir(parents=True, exist_ok=True)
        planned_write.path.write_bytes(planned_write.content)
        changed_paths.append(planned_write.path)
    return tuple(changed_paths)


def merge_required_items(existing_items: list[str], required_items: list[str]) -> list[str]:
    """Return ordered items with all required values present exactly once."""
    merged: list[str] = []
    for item in required_items:
        if item not in merged:
            merged.append(item)
    for item in existing_items:
        if item not in merged:
            merged.append(item)
    return merged


def as_string_list(raw_value: Any, path: Path, field_name: str) -> list[str]:
    """Normalize an optional string list field from package.json."""
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise GeneratorError(f"expected list for {field_name} in {path}")
    values: list[str] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, str):
            raise GeneratorError(f"expected string at {field_name}[{index}] in {path}")
        values.append(item)
    return values


def parse_string_mapping(raw_value: Any, path: Path, field_name: str) -> dict[str, str]:
    """Parse a mapping of string values."""
    mapping = require_inline_mapping(raw_value, path, field_name)
    return {str(key): require_inline_str(value, path, f"{field_name}.{key}") for key, value in mapping.items()}


def parse_yaml_mapping(raw_value: Any, path: Path, field_name: str) -> dict[str, Any]:
    """Parse a generic YAML mapping while normalizing keys to strings."""
    mapping = require_inline_mapping(raw_value, path, field_name)
    return {str(key): value for key, value in mapping.items()}


def parse_string_list(raw_value: Any, path: Path, field_name: str) -> list[str]:
    """Parse a list of strings."""
    return [require_inline_str(item, path, f"{field_name}[{index}]") for index, item in enumerate(parse_list(raw_value, path, field_name))]


def parse_list(raw_value: Any, path: Path, field_name: str) -> list[Any]:
    """Require a list value."""
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise GeneratorError(f"expected list for {field_name} in {path}")
    return list(raw_value)


def require_mapping(mapping: dict[str, Any], field_name: str, path: Path) -> dict[str, Any]:
    """Require a nested mapping field from a parent mapping."""
    if field_name not in mapping:
        raise GeneratorError(f"missing required field {field_name} in {path}")
    return require_inline_mapping(mapping[field_name], path, field_name)


def require_str(mapping: dict[str, Any], field_name: str, path: Path) -> str:
    """Require a nested string field from a parent mapping."""
    if field_name not in mapping:
        raise GeneratorError(f"missing required field {field_name} in {path}")
    return require_inline_str(mapping[field_name], path, field_name)


def require_bool(mapping: dict[str, Any], field_name: str, path: Path) -> bool:
    """Require a nested boolean field from a parent mapping."""
    if field_name not in mapping:
        raise GeneratorError(f"missing required field {field_name} in {path}")
    return require_inline_bool(mapping[field_name], path, field_name)


def require_inline_mapping(raw_value: Any, path: Path, field_name: str) -> dict[str, Any]:
    """Require an inline mapping value."""
    if not isinstance(raw_value, dict):
        raise GeneratorError(f"expected mapping for {field_name} in {path}")
    return raw_value


def require_inline_str(raw_value: Any, path: Path, field_name: str) -> str:
    """Require an inline string value."""
    if not isinstance(raw_value, str):
        raise GeneratorError(f"expected string for {field_name} in {path}")
    return raw_value


def require_optional_inline_str(raw_value: Any, path: Path, field_name: str) -> str | None:
    """Require an optional inline string value."""
    if raw_value is None:
        return None
    return require_inline_str(raw_value, path, field_name)


def require_inline_bool(raw_value: Any, path: Path, field_name: str) -> bool:
    """Require an inline boolean value."""
    if not isinstance(raw_value, bool):
        raise GeneratorError(f"expected boolean for {field_name} in {path}")
    return raw_value


def require_inline_int(raw_value: Any, path: Path, field_name: str) -> int:
    """Require an inline integer value."""
    if not isinstance(raw_value, int):
        raise GeneratorError(f"expected integer for {field_name} in {path}")
    return raw_value


def pascal_case(value: str) -> str:
    """Convert kebab-case plugin ids into PascalCase for function names."""
    return "".join(segment.capitalize() for segment in value.replace("_", "-").split("-") if segment)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
