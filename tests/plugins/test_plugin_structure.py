#!/usr/bin/env python3
"""Plugin structure validation tests.

Validates that each plugin has correct structure, file counts,
and no forbidden external references.
"""
import json
import os
import re
import unittest
from pathlib import Path

# Resolve plugins root relative to this test file
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"

EXPECTED_PLUGINS = {
    "ac-workflow",
    "ac-git",
    "ac-qa",
    "ac-tools",
    "ac-meta",
}

EXPECTED_COMMANDS: dict[str, set[str]] = {
    "ac-workflow": set(),
    "ac-git": set(),
    "ac-qa": set(),
    "ac-tools": set(),
    "ac-meta": set(),
}

EXPECTED_SKILLS = {
    "ac-workflow": {"mux", "mux-ospec", "mux-subagent", "product-manager",
                    "spec", "mux-roadmap"},
    "ac-git": {"git-find-fork", "git-safe", "gh-assets-branch-mgmt",
               "pull-request", "release", "branch", "worktree"},
    "ac-qa": {"e2e-review", "e2e-template", "gh-pr-review", "test-e2e",
              "playwright-cli", "browser", "prepare-app"},
    "ac-tools": {"gsuite", "human-agentic-design", "had", "cpc", "dr",
                 "dry-run", "single-file-uv-scripter", "ac-issue", "adr",
                 "agentic-export", "agentic-import", "agentic-share",
                 "milestone", "setup-voice-mode", "video-query",
                 "improve-agents-md"},
    "ac-meta": {"skill-writer", "hook-writer"},
}

# Patterns that indicate internal library dependencies (strictly forbidden)
FORBIDDEN_PATTERNS = [
    r'AGENTIC_GLOBAL',
    r'_AGENTIC_ROOT',
    r'~/.agents/agentic-config',
    r'core/lib/',
    r'core/tools/',
    r'core/prompts/',
    r'core/hooks/',
    r'core/scripts/',
]

# Allowed exceptions (context-based patterns)
ALLOWED_EXCEPTIONS = [
    r'~/.agents/customization/',  # User-data path, exempt (SC9)
    r'agentic_global_path',       # Config example in documentation (README)
    r'AGENTIC_CONFIG_PATH',       # Path resolution docs in improve-agents-md assets
    r'spec-resolver\.sh',         # External specs docs references in plugin skills
]


class TestPluginExists(unittest.TestCase):
    def test_all_plugins_exist(self) -> None:
        actual = {d.name for d in PLUGINS_DIR.iterdir() if d.is_dir()}
        self.assertEqual(actual, EXPECTED_PLUGINS)


class TestPluginManifest(unittest.TestCase):
    def test_each_plugin_has_valid_plugin_json(self) -> None:
        names: set[str] = set()
        for plugin in EXPECTED_PLUGINS:
            pj = PLUGINS_DIR / plugin / ".claude-plugin" / "plugin.json"
            self.assertTrue(pj.exists(), f"Missing plugin.json for {plugin}")
            data = json.loads(pj.read_text())
            self.assertIn("name", data)
            self.assertIn("version", data)
            self.assertIn("description", data)
            self.assertNotIn(data["name"], names, f"Duplicate name: {data['name']}")
            names.add(data["name"])


class TestCommandDistribution(unittest.TestCase):
    def test_commands_per_plugin(self) -> None:
        for plugin, expected in EXPECTED_COMMANDS.items():
            cmd_dir = PLUGINS_DIR / plugin / "commands"
            if expected:
                self.assertTrue(cmd_dir.exists(), f"Missing commands/ for {plugin}")
                actual = {f.name for f in cmd_dir.iterdir() if f.suffix == ".md"}
                self.assertEqual(actual, expected, f"Command mismatch for {plugin}")
            else:
                # Zero commands expected: commands/ dir must NOT exist
                self.assertFalse(cmd_dir.exists(), f"Unexpected commands/ dir for {plugin}")


class TestSkillDistribution(unittest.TestCase):
    def test_skills_per_plugin(self) -> None:
        for plugin, expected in EXPECTED_SKILLS.items():
            skills_dir = PLUGINS_DIR / plugin / "skills"
            if expected:
                self.assertTrue(skills_dir.exists(), f"Missing skills/ for {plugin}")
                actual = {d.name for d in skills_dir.iterdir() if d.is_dir()}
                self.assertEqual(actual, expected, f"Skill mismatch for {plugin}")
            # If no skills expected, skills/ dir may not exist (OK)

    def test_each_skill_has_skill_md(self) -> None:
        for plugin in EXPECTED_PLUGINS:
            skills_dir = PLUGINS_DIR / plugin / "skills"
            if not skills_dir.exists():
                continue
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    self.assertTrue(
                        (skill_dir / "SKILL.md").exists(),
                        f"Missing SKILL.md in {skill_dir}",
                    )


class TestNoForbiddenLibraryDeps(unittest.TestCase):
    """Verify no forbidden internal library references remain."""

    def test_no_forbidden_patterns_in_plugins(self) -> None:
        violations: list[str] = []
        for root, _dirs, files in os.walk(PLUGINS_DIR):
            # Skip test directories — tests legitimately reference patterns they validate
            if "/tests/" in root + "/" or root.endswith("/tests"):
                continue
            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix not in (".md", ".sh", ".py", ".json"):
                    continue
                content = fpath.read_text(errors="replace")
                for pattern in FORBIDDEN_PATTERNS:
                    matches = list(re.finditer(pattern, content))
                    if matches:
                        for match in matches:
                            context_start = max(0, match.start() - 50)
                            context = content[context_start:match.start() + 100]
                            # Check allowed exceptions
                            is_allowed = any(
                                re.search(exc, context) for exc in ALLOWED_EXCEPTIONS
                            )
                            # Also allow comment-only lines for agentic-root.sh references
                            line_start = content.rfind('\n', 0, match.start()) + 1
                            line_end = content.find('\n', match.end())
                            line = content[line_start:line_end if line_end != -1 else None].strip()
                            is_comment = line.startswith('#')
                            if not is_allowed and not is_comment:
                                violations.append(
                                    f"{fpath.relative_to(REPO_ROOT)}: "
                                    f"forbidden pattern '{pattern}'"
                                )
                                break  # One violation per pattern per file
        self.assertEqual(violations, [], "\n".join(violations))


class TestNoParentDirectoryTraversal(unittest.TestCase):
    def test_no_parent_directory_traversal_in_plugin_json(self) -> None:
        """Plugin manifests and hooks.json must not reference ../."""
        violations: list[str] = []
        for plugin in EXPECTED_PLUGINS:
            plugin_dir = PLUGINS_DIR / plugin
            for json_file in [
                plugin_dir / ".claude-plugin" / "plugin.json",
                plugin_dir / "hooks" / "hooks.json",
            ]:
                if not json_file.exists():
                    continue
                content = json_file.read_text(errors="replace")
                if "../" in content:
                    violations.append(str(json_file.relative_to(REPO_ROOT)))
        self.assertEqual(violations, [], f"Parent traversal in plugin manifests: {violations}")

    def test_no_escape_traversal_in_scripts(self) -> None:
        """Shell scripts must not use ../ to escape plugin root (ln -sf ../../ within cd subshells is OK)."""
        violations: list[str] = []
        for root, _dirs, files in os.walk(PLUGINS_DIR):
            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix not in (".sh",):
                    continue
                content = fpath.read_text(errors="replace")
                for line_num, line in enumerate(content.splitlines(), 1):
                    # Only flag source or import statements with ../
                    stripped = line.strip()
                    if re.search(r'source\s+.*\.\./', line) or re.search(r'^\.\s+.*\.\./', line):
                        if not stripped.startswith('#'):
                            violations.append(
                                f"{fpath.relative_to(REPO_ROOT)}:{line_num}: "
                                f"parent traversal in source: {stripped[:80]}"
                            )
        self.assertEqual(violations, [], "\n".join(violations))


class TestSpecResolver(unittest.TestCase):
    def test_spec_resolver_exists_in_ac_workflow(self) -> None:
        sr = PLUGINS_DIR / "ac-workflow" / "scripts" / "spec-resolver.sh"
        self.assertTrue(sr.exists())

    def test_branch_skill_dependencies_exist_in_ac_git(self) -> None:
        required = [
            PLUGINS_DIR / "ac-git" / "scripts" / "spec-resolver.sh",
            PLUGINS_DIR / "ac-git" / "scripts" / "external-specs.sh",
            PLUGINS_DIR / "ac-git" / "scripts" / "lib" / "config-loader.sh",
        ]
        for path in required:
            self.assertTrue(path.exists(), f"Missing branch dependency: {path}")

    def test_spec_resolver_uses_plugin_root(self) -> None:
        sr = PLUGINS_DIR / "ac-workflow" / "scripts" / "spec-resolver.sh"
        content = sr.read_text()
        self.assertIn("CLAUDE_PLUGIN_ROOT", content)
        self.assertNotIn("AGENTIC_GLOBAL", content)
        self.assertNotIn("_AGENTIC_ROOT", content)

    def test_config_loader_exists_in_ac_workflow(self) -> None:
        cl = PLUGINS_DIR / "ac-workflow" / "scripts" / "lib" / "config-loader.sh"
        self.assertTrue(cl.exists())

    def test_spec_stage_agents_use_plugin_root(self) -> None:
        spec_agents_dir = PLUGINS_DIR / "ac-workflow" / "agents" / "spec"
        violations = []
        for agent_file in spec_agents_dir.glob("*.md"):
            content = agent_file.read_text()
            if "AGENTIC_GLOBAL" in content or "core/lib/spec-resolver" in content:
                violations.append(str(agent_file.name))
        self.assertEqual(violations, [], f"Agents still reference AGENTIC_GLOBAL: {violations}")


class TestHooksDistribution(unittest.TestCase):
    def test_ac_tools_has_hooks(self) -> None:
        hj = PLUGINS_DIR / "ac-tools" / "hooks" / "hooks.json"
        self.assertTrue(hj.exists())
        data = json.loads(hj.read_text())
        hooks = data["hooks"]["PreToolUse"]
        self.assertEqual(len(hooks), 2, "ac-tools should have 2 hooks")

    def test_hooks_use_plugin_root(self) -> None:
        for plugin in ["ac-tools", "ac-git"]:
            hj = PLUGINS_DIR / plugin / "hooks" / "hooks.json"
            if hj.exists():
                content = hj.read_text()
                self.assertIn("CLAUDE_PLUGIN_ROOT", content)
                self.assertNotIn("AGENTIC_GLOBAL", content)


class TestMuxPythonTools(unittest.TestCase):
    def test_mux_tools_exist(self) -> None:
        tools_dir = PLUGINS_DIR / "ac-workflow" / "scripts" / "tools"
        expected_tools = {
            "spawn.py", "spec.py", "researcher.py", "ospec.py",
            "oresearch.py", "coordinator.py", "campaign.py",
        }
        for tool in expected_tools:
            self.assertTrue(
                (tools_dir / tool).exists(),
                f"Missing tool: {tool}",
            )

    def test_mux_prompts_exist(self) -> None:
        prompts_dir = PLUGINS_DIR / "ac-workflow" / "scripts" / "prompts"
        count = sum(1 for _ in prompts_dir.rglob("*.md"))
        self.assertEqual(count, 10, f"Expected 10 prompt files, found {count}")


class TestImproveAgentsMdSkillStructure(unittest.TestCase):
    """Validate improve-agents-md skill has required structure."""

    SKILL_DIR = PLUGINS_DIR / "ac-tools" / "skills" / "improve-agents-md"

    def test_skill_md_exists(self) -> None:
        self.assertTrue((self.SKILL_DIR / "SKILL.md").exists())

    def test_tools_dir_exists(self) -> None:
        self.assertTrue((self.SKILL_DIR / "tools").is_dir())

    def test_required_tools_exist(self) -> None:
        expected_tools = {
            "bootstrap.py", "project_type.py", "template_engine.py",
            "preserve_custom.py",
        }
        tools_dir = self.SKILL_DIR / "tools"
        actual = {f.name for f in tools_dir.glob("*.py")}
        self.assertEqual(actual, expected_tools)

    def test_assets_dir_exists(self) -> None:
        self.assertTrue((self.SKILL_DIR / "assets").is_dir())

    def test_assets_templates_exist(self) -> None:
        templates_dir = self.SKILL_DIR / "assets" / "templates"
        self.assertTrue(templates_dir.is_dir())

    def test_each_template_has_content(self) -> None:
        """Every template directory must contain at least one file."""
        templates_dir = self.SKILL_DIR / "assets" / "templates"
        for tdir in templates_dir.iterdir():
            if tdir.is_dir():
                files = list(tdir.iterdir())
                self.assertTrue(len(files) > 0,
                                f"Template dir '{tdir.name}' is empty")


class TestMarketplaceJson(unittest.TestCase):
    """Validate .claude-plugin/marketplace.json schema and consistency."""

    MP_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

    def test_marketplace_json_exists(self) -> None:
        self.assertTrue(self.MP_PATH.exists())

    def test_marketplace_json_valid(self) -> None:
        data = json.loads(self.MP_PATH.read_text())
        self.assertIn("name", data)
        self.assertIn("plugins", data)
        self.assertIsInstance(data["plugins"], list)

    def test_marketplace_declares_all_5_plugins(self) -> None:
        data = json.loads(self.MP_PATH.read_text())
        names = {p["name"] for p in data["plugins"]}
        self.assertEqual(names, EXPECTED_PLUGINS)

    def test_marketplace_plugin_entries_have_required_fields(self) -> None:
        data = json.loads(self.MP_PATH.read_text())
        for entry in data["plugins"]:
            self.assertIn("name", entry, f"Missing name in {entry}")
            self.assertIn("source", entry, f"Missing source in {entry}")
            self.assertIn("description", entry, f"Missing description in {entry}")

    def test_marketplace_source_paths_exist(self) -> None:
        data = json.loads(self.MP_PATH.read_text())
        for entry in data["plugins"]:
            source = entry["source"]
            # source is relative like ./plugins/ac-git -- strip leading ./
            source_path = REPO_ROOT / source.lstrip("./")
            self.assertTrue(source_path.is_dir(),
                            f"Source path does not exist: {source}")

    def test_marketplace_skill_counts_match(self) -> None:
        """Verify skill count per plugin matches actual skill directories."""
        data = json.loads(self.MP_PATH.read_text())
        for entry in data["plugins"]:
            name = entry["name"]
            skills_dir = PLUGINS_DIR / name / "skills"
            if skills_dir.exists():
                actual_count = len([d for d in skills_dir.iterdir() if d.is_dir()])
                expected_count = len(EXPECTED_SKILLS.get(name, set()))
                self.assertEqual(actual_count, expected_count,
                                 f"{name}: skill count mismatch "
                                 f"(actual={actual_count}, expected={expected_count})")

    def test_marketplace_descriptions_match_plugin_json(self) -> None:
        """Verify marketplace description matches each plugin.json description."""
        data = json.loads(self.MP_PATH.read_text())
        for entry in data["plugins"]:
            name = entry["name"]
            pj = PLUGINS_DIR / name / ".claude-plugin" / "plugin.json"
            if pj.exists():
                pj_data = json.loads(pj.read_text())
                self.assertEqual(entry["description"], pj_data["description"],
                                 f"{name}: marketplace vs plugin.json description mismatch")


class TestNoLegacyReferences(unittest.TestCase):
    """Verify no stale legacy plugin names remain in test files."""

    LEGACY_NAMES = [
        "agentic-spec", "agentic-git", "agentic-review",
        "agentic-tools", "agentic-mux",
    ]

    def test_no_legacy_names_in_plugin_tests(self) -> None:
        """No test file under tests/plugins/ should reference old plugin names.

        Excludes this file itself, since it defines the LEGACY_NAMES list.
        """
        tests_dir = REPO_ROOT / "tests" / "plugins"
        this_file = Path(__file__).name
        violations: list[str] = []
        for f in tests_dir.glob("*.py"):
            if f.name == this_file:
                continue  # skip self (contains LEGACY_NAMES definition)
            content = f.read_text()
            for name in self.LEGACY_NAMES:
                if name in content:
                    violations.append(f"{f.name}: references '{name}'")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_no_legacy_names_in_plugin_skills(self) -> None:
        """No SKILL.md should reference old plugin names in instructions."""
        violations: list[str] = []
        for plugin in EXPECTED_PLUGINS:
            skills_dir = PLUGINS_DIR / plugin / "skills"
            if not skills_dir.exists():
                continue
            for skill_dir in skills_dir.iterdir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    content = skill_md.read_text()
                    for name in self.LEGACY_NAMES:
                        if name in content:
                            violations.append(
                                f"{plugin}/{skill_dir.name}/SKILL.md: "
                                f"references '{name}'"
                            )
        self.assertEqual(violations, [], "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
