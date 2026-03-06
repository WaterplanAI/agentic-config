#!/usr/bin/env python3
"""B-003 Validation Script.

Validates marketplace submission and team distribution deliverables:
- SC-1: Self-hosted marketplace functional (marketplace.json on main-ready branch)
- SC-2: Plugin marketplace add works (5 plugins listed)
- SC-3: All 5 plugins installable (plugin.json exists for each)
- SC-4: Per-plugin README quality
- SC-5: Version management operational
- SC-6: Team adoption via settings.json
- SC-7: Auto-prompt on trust (template correctness)
- SC-8: No config collisions (documentation exists)
- SC-9: Adoption tiers documented

Usage: python3 tests/b003-validate.py
"""
import json
import sys
from pathlib import Path

PASS = 0
FAIL = 0

PLUGINS = ["ac-workflow", "ac-git", "ac-qa", "ac-tools", "ac-meta"]

README_REQUIRED_SECTIONS = ["Installation", "Skills", "Usage Examples", "License"]


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {label}")
    else:
        FAIL += 1
        print(f"  FAIL: {label} -- {detail}")


def main() -> None:
    global PASS, FAIL
    root = Path(__file__).resolve().parent.parent

    # ===== SC-1: Self-hosted marketplace functional =====
    print("\nSC-1: Self-hosted marketplace functional")
    mp_path = root / ".claude-plugin" / "marketplace.json"
    check("marketplace.json exists", mp_path.exists())
    if mp_path.exists():
        mp = json.loads(mp_path.read_text())
        check("marketplace name is agentic-plugins", mp.get("name") == "agentic-plugins")
        check("plugins array exists", isinstance(mp.get("plugins"), list))
        check("5 plugins listed", len(mp.get("plugins", [])) == 5, f"found {len(mp.get('plugins', []))}")

    # ===== SC-2: Plugin marketplace add (structural) =====
    print("\nSC-2: Plugin marketplace add (structural)")
    if mp_path.exists():
        mp = json.loads(mp_path.read_text())
        plugin_names = {p.get("name") for p in mp.get("plugins", [])}
        for name in PLUGINS:
            check(f"{name} in marketplace.json", name in plugin_names)
        for p in mp.get("plugins", []):
            name = p.get("name", "?")
            check(f"{name}: has source field", "source" in p)
            check(f"{name}: has description", bool(p.get("description")))
            source_path = root / p.get("source", "")
            check(f"{name}: source directory exists", source_path.is_dir(), str(source_path))

    # ===== SC-3: All 5 plugins installable =====
    print("\nSC-3: All 5 plugins installable")
    for name in PLUGINS:
        pj = root / "plugins" / name / ".claude-plugin" / "plugin.json"
        check(f"{name}: plugin.json exists", pj.exists())
        if pj.exists():
            pdata = json.loads(pj.read_text())
            check(f"{name}: name matches", pdata.get("name") == name)
            check(f"{name}: version is semver", _is_semver(pdata.get("version", "")), pdata.get("version", ""))
            check(f"{name}: has description", bool(pdata.get("description")))
            check(f"{name}: has author.name", bool(pdata.get("author", {}).get("name")))
            check(f"{name}: has license", bool(pdata.get("license")))

    # ===== SC-4: Per-plugin README quality =====
    print("\nSC-4: Per-plugin README quality")
    for name in PLUGINS:
        readme = root / "plugins" / name / "README.md"
        check(f"{name}: README.md exists", readme.exists())
        if readme.exists():
            content = readme.read_text()
            for section in README_REQUIRED_SECTIONS:
                check(f"{name}: has '{section}' section", f"## {section}" in content or f"# {section}" in content)
            # Check for plugin-specific content
            check(f"{name}: has Skills or Agents section", "## Skills" in content or "## Agents" in content or "Skill" in content)
            check(f"{name}: >30 lines", len(content.splitlines()) > 30, f"{len(content.splitlines())} lines")
            check(f"{name}: has marketplace install command", "agentic-plugins" in content)

    # ===== SC-5: Version management operational =====
    print("\nSC-5: Version management operational")
    for name in PLUGINS:
        pj = root / "plugins" / name / ".claude-plugin" / "plugin.json"
        if pj.exists():
            pdata = json.loads(pj.read_text())
            check(f"{name}: version is semver", _is_semver(pdata.get("version", "")))
    # Check marketplace has no version duplication
    if mp_path.exists():
        mp = json.loads(mp_path.read_text())
        for p in mp.get("plugins", []):
            check(f"{p.get('name')}: no version in marketplace entry", "version" not in p)
    # Check CHANGELOG exists
    changelog = root / "CHANGELOG.md"
    check("CHANGELOG.md exists", changelog.exists())
    if changelog.exists():
        cl_content = changelog.read_text()
        check("CHANGELOG has [Unreleased] section", "[Unreleased]" in cl_content)

    # ===== SC-6: Team adoption via settings.json =====
    print("\nSC-6: Team adoption via settings.json")
    template = root / "templates" / "team-settings.json"
    check("team-settings.json template exists", template.exists())
    if template.exists():
        tcontent = template.read_text()
        check("template has extraKnownMarketplaces", "extraKnownMarketplaces" in tcontent)
        check("template has enabledPlugins", "enabledPlugins" in tcontent)
        check("template has agentic-plugins marketplace", "agentic-plugins" in tcontent)
        check("template references github source", '"github"' in tcontent)
        # Verify all plugins are listed
        for name in PLUGINS:
            check(f"template enables {name}", f"{name}@agentic-plugins" in tcontent)

    # ===== SC-7: Auto-prompt on trust =====
    print("\nSC-7: Auto-prompt on trust (template structure)")
    if template.exists():
        tcontent = template.read_text()
        # Auto-prompt requires both extraKnownMarketplaces and enabledPlugins
        check(
            "template has both marketplace ref and enabled plugins",
            "extraKnownMarketplaces" in tcontent and "enabledPlugins" in tcontent,
        )

    distribution_doc = root / "docs" / "distribution.md"
    check(
        "distribution docs mention auto-prompt",
        distribution_doc.exists() and "auto-prompt" in distribution_doc.read_text().lower()
        if distribution_doc.exists() else False,
    )

    # ===== SC-8: No config collisions =====
    print("\nSC-8: No config collisions")
    if distribution_doc.exists():
        dist_content = distribution_doc.read_text()
        check(
            "distribution docs cover collision prevention",
            "collision" in dist_content.lower(),
        )
        check(
            "distribution docs explain additive behavior",
            "additive" in dist_content.lower(),
        )

    # ===== SC-9: Adoption tiers documented =====
    print("\nSC-9: Adoption tiers documented")
    check("distribution.md exists", distribution_doc.exists())
    if distribution_doc.exists():
        dist_content = distribution_doc.read_text()
        check(
            "documents Tier 1 (Global)",
            "tier 1" in dist_content.lower() or "global" in dist_content.lower(),
        )
        check(
            "documents Tier 2 (Team-Recommended)",
            "tier 2" in dist_content.lower() or "team" in dist_content.lower(),
        )
        check(
            "documents Tier 3 (Selective)",
            "tier 3" in dist_content.lower() or "selective" in dist_content.lower(),
        )
        check("has concrete JSON examples", '"enabledPlugins"' in dist_content)
        check("has install commands", "claude plugin install" in dist_content)
        check("covers GITHUB_TOKEN", "GITHUB_TOKEN" in dist_content)
        check(
            "covers strictKnownMarketplaces",
            "strictKnownMarketplaces" in dist_content,
        )
        check("covers fork workflow", "fork" in dist_content.lower())

    # ===== Summary =====
    print(f"\n{'='*50}")
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    print(f"{'='*50}")
    sys.exit(1 if FAIL > 0 else 0)


def _is_semver(version: str) -> bool:
    """Check if version string matches basic semver pattern."""
    import re
    return bool(re.match(r'^\d+\.\d+\.\d+', version))


if __name__ == "__main__":
    main()
