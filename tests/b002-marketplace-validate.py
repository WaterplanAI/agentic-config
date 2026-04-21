#!/usr/bin/env python3
"""B-002 Marketplace Validation Script.

Validates marketplace.json schema, plugin entries, and cross-references
against individual plugin.json manifests.

Usage: python3 tests/b002-marketplace-validate.py
"""
import json
import sys
from pathlib import Path

LEGACY_PLUGIN_NAMES = [
    "agentic-spec", "agentic-git", "agentic-review",
    "agentic-tools", "agentic-mux",
]

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {label}")
    else:
        FAIL += 1
        print(f"  FAIL: {label} -- {detail}")


def discover_expected_plugin_names(root: Path) -> set[str]:
    """Return marketplace plugin names from shipped plugin manifests."""
    plugins_dir = root / "plugins"
    return {
        plugin_dir.name
        for plugin_dir in plugins_dir.iterdir()
        if plugin_dir.is_dir() and (plugin_dir / ".claude-plugin" / "plugin.json").exists()
    }


def main() -> None:
    global PASS, FAIL
    root = Path(__file__).resolve().parent.parent
    mp_path = root / ".claude-plugin" / "marketplace.json"

    # --- SC-1: marketplace.json exists ---
    print("SC-1: marketplace.json exists")
    check("file exists", mp_path.exists(), str(mp_path))
    if not mp_path.exists():
        print(f"\nRESULT: {PASS} passed, {FAIL} failed")
        sys.exit(1)

    mp = json.loads(mp_path.read_text())

    # --- SC-1: required top-level fields ---
    print("SC-1: required top-level fields")
    check("name field", "name" in mp)
    check("name is kebab-case", mp.get("name", "").replace("-", "").isalpha(), mp.get("name", ""))
    check("owner field", "owner" in mp)
    check("owner.name field", "name" in mp.get("owner", {}))
    check("plugins field", "plugins" in mp)
    check("plugins is array", isinstance(mp.get("plugins"), list))

    # --- SC-9: no reserved names ---
    print("SC-9: no reserved names")
    reserved = {
        "claude-code-marketplace", "claude-code-plugins", "claude-plugins-official",
        "anthropic-marketplace", "anthropic-plugins", "agent-skills", "life-sciences",
    }
    check("marketplace name not reserved", mp.get("name") not in reserved, mp.get("name", ""))

    # --- SC-2: all marketplace plugins listed ---
    plugins = mp.get("plugins", [])
    expected_names = discover_expected_plugin_names(root)
    expected_count = len(expected_names)
    print(f"SC-2: all {expected_count} marketplace plugins listed")
    check(f"{expected_count} plugins", len(plugins) == expected_count, f"found {len(plugins)}")
    actual_names = {p.get("name") for p in plugins}
    check("correct plugin names", actual_names == expected_names, f"got {actual_names}")

    # --- SC-9: unique names ---
    print("SC-9: unique plugin names")
    names = [p.get("name") for p in plugins]
    check("no duplicate names", len(names) == len(set(names)), f"duplicates: {[n for n in names if names.count(n) > 1]}")

    # --- SC-10: no version in marketplace plugin entries ---
    print("SC-10: no version duplication in marketplace entries")
    for p in plugins:
        check(f"{p.get('name')}: no version field", "version" not in p)

    # --- SC-2: correct sources, descriptions, categories ---
    print("SC-2: plugin entry fields")
    for p in plugins:
        name = p.get("name", "?")
        check(f"{name}: has source", "source" in p)
        check(f"{name}: source is relative", p.get("source", "").startswith("./plugins/"), p.get("source", ""))
        check(f"{name}: has description", "description" in p and len(p.get("description", "")) > 0)
        check(f"{name}: has category", "category" in p)
        check(f"{name}: has tags", "tags" in p and isinstance(p.get("tags"), list))

    # --- Cross-reference against plugin.json files ---
    print("Cross-reference: marketplace entries vs plugin.json")
    for p in plugins:
        name = p.get("name", "?")
        pj_path = root / "plugins" / name / ".claude-plugin" / "plugin.json"
        check(f"{name}: plugin.json exists", pj_path.exists(), str(pj_path))
        if pj_path.exists():
            pj = json.loads(pj_path.read_text())
            check(f"{name}: name matches", pj.get("name") == name, f"plugin.json={pj.get('name')}")
            check(f"{name}: description matches", p.get("description") == pj.get("description"),
                  f"mp='{p.get('description')}' vs pj='{pj.get('description')}'")
            check(f"{name}: version in plugin.json", "version" in pj)

    # --- Root plugin.json consistency ---
    print("Root plugin.json consistency")
    root_pj_path = root / ".claude-plugin" / "plugin.json"
    if root_pj_path.exists():
        root_pj = json.loads(root_pj_path.read_text())
        check("root author.name consistent", root_pj.get("author", {}).get("name") == "Agentic Config Contributors",
              root_pj.get("author", {}).get("name", ""))
        check("root has homepage", "homepage" in root_pj)

    # --- Schema compatibility ---
    print("Schema and metadata")
    allowed_root_keys = {"name", "owner", "metadata", "plugins"}
    extra_root_keys = sorted(set(mp) - allowed_root_keys)
    check("no unsupported root keys", len(extra_root_keys) == 0, ", ".join(extra_root_keys))
    check("has metadata.description", "description" in mp.get("metadata", {}))
    check("has metadata.pluginRoot", "pluginRoot" in mp.get("metadata", {}))

    # --- Skill count cross-reference ---
    print("Skill count cross-reference")
    for p in plugins:
        name = p.get("name", "?")
        skills_dir = root / "plugins" / name / "skills"
        if skills_dir.exists():
            skill_count = len([d for d in skills_dir.iterdir() if d.is_dir()])
            check(f"{name}: has skills", skill_count > 0, f"found {skill_count}")

    # --- No legacy names in test files ---
    print("No legacy plugin names in test files")
    tests_dir = root / "tests" / "plugins"
    this_file = Path(__file__).name
    # Exclude files that define the LEGACY_NAMES list itself
    excluded_files = {this_file, "test_plugin_structure.py"}
    legacy_found: list[str] = []
    for f in tests_dir.glob("*.py"):
        if f.name in excluded_files:
            continue
        content = f.read_text()
        for ln in LEGACY_PLUGIN_NAMES:
            if ln in content:
                legacy_found.append(f"{f.name}: '{ln}'")
    check("no legacy names in tests/plugins/", len(legacy_found) == 0,
          "; ".join(legacy_found))

    # --- Summary ---
    total = PASS + FAIL
    print(f"\nRESULT: {PASS}/{total} passed, {FAIL} failed")
    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()
