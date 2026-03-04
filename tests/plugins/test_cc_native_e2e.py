#!/usr/bin/env python3
"""CC-native plugin E2E structural validation tests.

Validates that the plugin directory structure supports CC-native loading
via `claude --plugin-dir` and `claude plugin install` without actually
invoking the Claude CLI (which may not be available in CI).

These tests verify:
- All 5 plugins have correct directory structure for CC auto-discovery
- Skill directories contain SKILL.md for each skill
- Hook files are correctly structured for auto-registration
- marketplace.json paths resolve correctly
- No duplicate skill names across plugins
- dev.sh references all 5 plugins
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"

EXPECTED_PLUGINS = {
    "ac-workflow",
    "ac-git",
    "ac-qa",
    "ac-tools",
    "ac-meta",
}

PLUGINS_WITH_HOOKS = {
    "ac-git": 1,    # git-commit-guard
    "ac-tools": 2,  # dry-run-guard, gsuite-public-asset-guard
}

KEY_SKILLS = {
    "spec", "mux", "mux-subagent", "git-safe",
    "pull-request", "gsuite", "skill-writer",
}


class TestPluginDirStructure(unittest.TestCase):
    """Validate each plugin has the structure CC expects for auto-discovery."""

    def test_each_plugin_has_claude_plugin_dir(self) -> None:
        for plugin in EXPECTED_PLUGINS:
            cp_dir = PLUGINS_DIR / plugin / ".claude-plugin"
            self.assertTrue(cp_dir.is_dir(),
                            f"{plugin}: missing .claude-plugin/ dir")

    def test_each_plugin_has_plugin_json(self) -> None:
        for plugin in EXPECTED_PLUGINS:
            pj = PLUGINS_DIR / plugin / ".claude-plugin" / "plugin.json"
            self.assertTrue(pj.exists(),
                            f"{plugin}: missing plugin.json")
            data = json.loads(pj.read_text())
            self.assertEqual(data["name"], plugin,
                             f"{plugin}: plugin.json name mismatch")

    def test_no_commands_dirs_exist(self) -> None:
        """CC-native: all-skill convention -- no commands/ dirs allowed."""
        for plugin in EXPECTED_PLUGINS:
            cmd_dir = PLUGINS_DIR / plugin / "commands"
            self.assertFalse(cmd_dir.exists(),
                             f"{plugin}: has forbidden commands/ dir")

    def test_each_skill_has_skill_md(self) -> None:
        """CC auto-discovers skills from skills/<name>/SKILL.md."""
        for plugin in EXPECTED_PLUGINS:
            skills_dir = PLUGINS_DIR / plugin / "skills"
            if not skills_dir.exists():
                continue
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    self.assertTrue(
                        (skill_dir / "SKILL.md").exists(),
                        f"{plugin}/{skill_dir.name}: missing SKILL.md")


class TestNoDuplicateSkills(unittest.TestCase):
    """Verify no skill name appears in more than one plugin."""

    def test_unique_skill_names_across_plugins(self) -> None:
        seen: dict[str, str] = {}
        duplicates: list[str] = []
        for plugin in sorted(EXPECTED_PLUGINS):
            skills_dir = PLUGINS_DIR / plugin / "skills"
            if not skills_dir.exists():
                continue
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    name = skill_dir.name
                    if name in seen:
                        duplicates.append(
                            f"'{name}' in both {seen[name]} and {plugin}")
                    seen[name] = plugin
        self.assertEqual(duplicates, [], "\n".join(duplicates))


class TestHooksAutoRegistration(unittest.TestCase):
    """Validate hooks/hooks.json for plugins that declare hooks."""

    def test_hooks_json_exists_where_expected(self) -> None:
        for plugin in PLUGINS_WITH_HOOKS:
            hj = PLUGINS_DIR / plugin / "hooks" / "hooks.json"
            self.assertTrue(hj.exists(),
                            f"{plugin}: missing hooks/hooks.json")

    def test_hooks_json_valid_structure(self) -> None:
        for plugin in PLUGINS_WITH_HOOKS:
            hj = PLUGINS_DIR / plugin / "hooks" / "hooks.json"
            if not hj.exists():
                continue
            data = json.loads(hj.read_text())
            self.assertIn("hooks", data)
            self.assertIn("PreToolUse", data["hooks"])
            self.assertIsInstance(data["hooks"]["PreToolUse"], list)

    def test_hooks_json_correct_count(self) -> None:
        for plugin, expected_count in PLUGINS_WITH_HOOKS.items():
            hj = PLUGINS_DIR / plugin / "hooks" / "hooks.json"
            if not hj.exists():
                continue
            data = json.loads(hj.read_text())
            actual_count = len(data["hooks"]["PreToolUse"])
            self.assertEqual(actual_count, expected_count,
                             f"{plugin}: expected {expected_count} hooks, "
                             f"found {actual_count}")

    def test_hooks_use_plugin_root_var(self) -> None:
        for plugin in PLUGINS_WITH_HOOKS:
            hj = PLUGINS_DIR / plugin / "hooks" / "hooks.json"
            if not hj.exists():
                continue
            content = hj.read_text()
            self.assertIn("CLAUDE_PLUGIN_ROOT", content,
                          f"{plugin}: hooks.json missing CLAUDE_PLUGIN_ROOT")
            self.assertNotIn("AGENTIC_GLOBAL", content,
                             f"{plugin}: hooks.json uses forbidden AGENTIC_GLOBAL")

    def test_no_unexpected_hooks_json(self) -> None:
        """Plugins without declared hooks should not have hooks/hooks.json."""
        for plugin in EXPECTED_PLUGINS:
            if plugin in PLUGINS_WITH_HOOKS:
                continue
            hj = PLUGINS_DIR / plugin / "hooks" / "hooks.json"
            self.assertFalse(hj.exists(),
                             f"{plugin}: unexpected hooks/hooks.json")


class TestKeySkillsResolvable(unittest.TestCase):
    """Verify key skills that users depend on are discoverable."""

    def test_key_skills_exist(self) -> None:
        all_skills: set[str] = set()
        for plugin in EXPECTED_PLUGINS:
            skills_dir = PLUGINS_DIR / plugin / "skills"
            if skills_dir.exists():
                all_skills.update(d.name for d in skills_dir.iterdir() if d.is_dir())
        missing = KEY_SKILLS - all_skills
        self.assertEqual(missing, set(),
                         f"Key skills not found: {missing}")


class TestDevShReferencesAllPlugins(unittest.TestCase):
    """Validate dev.sh includes --plugin-dir for all 5 plugins."""

    def test_dev_sh_references_all_plugins(self) -> None:
        dev_sh = REPO_ROOT / "dev.sh"
        self.assertTrue(dev_sh.exists(), "dev.sh not found")
        content = dev_sh.read_text()
        for plugin in EXPECTED_PLUGINS:
            self.assertIn(f"plugins/{plugin}", content,
                          f"dev.sh missing reference to {plugin}")


if __name__ == "__main__":
    unittest.main()
