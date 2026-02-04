#!/usr/bin/env python3
"""
Validate mux-ospec skill directory structure.

Tests:
- Required files exist (SKILL.md, tools/, agents/)
- SKILL.md frontmatter is valid
- Tool scripts are executable
- Agent definitions follow conventions
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///

from __future__ import annotations

import re
from pathlib import Path

import yaml

# Resolve skill root relative to test file
SKILL_ROOT = Path(__file__).parent.parent


class TestSkillStructure:
    """Validate skill directory structure."""

    def test_skill_md_exists(self) -> None:
        """SKILL.md must exist at skill root."""
        skill_md = SKILL_ROOT / "SKILL.md"
        assert skill_md.exists(), f"SKILL.md not found at {skill_md}"

    def test_tools_directory_exists(self) -> None:
        """tools/ directory must exist."""
        tools_dir = SKILL_ROOT / "tools"
        assert tools_dir.exists(), "tools/ directory required"
        assert tools_dir.is_dir(), "tools must be a directory"

    def test_agents_directory_exists(self) -> None:
        """agents/ directory must exist."""
        agents_dir = SKILL_ROOT / "agents"
        assert agents_dir.exists(), "agents/ directory required"
        assert agents_dir.is_dir(), "agents must be a directory"

    def test_cookbook_directory_exists(self) -> None:
        """cookbook/ directory should exist for edge case docs."""
        cookbook_dir = SKILL_ROOT / "cookbook"
        assert cookbook_dir.exists(), "cookbook/ directory expected"

    def test_tests_directory_exists(self) -> None:
        """tests/ directory must exist."""
        tests_dir = SKILL_ROOT / "tests"
        assert tests_dir.exists(), "tests/ directory required"


class TestSkillMdFrontmatter:
    """Validate SKILL.md frontmatter format."""

    def _parse_frontmatter(self) -> dict:
        """Extract YAML frontmatter from SKILL.md.

        Note: Some frontmatter values contain colons that YAML interprets
        as key-value separators. We parse line-by-line for robustness.
        """
        skill_md = SKILL_ROOT / "SKILL.md"
        content = skill_md.read_text()

        # Match frontmatter between --- delimiters
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        assert match, "SKILL.md must have YAML frontmatter"

        fm_text = match.group(1)

        # Try standard YAML parse first
        try:
            return yaml.safe_load(fm_text)
        except yaml.YAMLError:
            # Fallback: parse line-by-line for unquoted values with colons
            result: dict = {}
            current_list_key: str | None = None
            current_list: list[str] = []

            for line in fm_text.split("\n"):
                # List item (part of previous key)
                if line.startswith("  - "):
                    current_list.append(line[4:].strip())
                # New key-value pair (or key with no value that starts a list)
                elif ":" in line and not line.startswith(" "):
                    # Save previous list if any
                    if current_list_key and current_list:
                        result[current_list_key] = current_list
                        current_list = []
                        current_list_key = None

                    # Split on first colon only
                    parts = line.split(":", 1)
                    key = parts[0].strip()
                    value = parts[1].strip() if len(parts) > 1 else ""

                    # Handle boolean/none values
                    if value.lower() == "true":
                        result[key] = True
                    elif value.lower() == "false":
                        result[key] = False
                    elif value == "" or value.lower() == "null":
                        # Empty value might indicate a list follows
                        current_list_key = key
                    else:
                        result[key] = value

            # Save final list
            if current_list_key and current_list:
                result[current_list_key] = current_list

            return result

    def test_name_field_exists(self) -> None:
        """Frontmatter must have 'name' field."""
        fm = self._parse_frontmatter()
        assert "name" in fm, "frontmatter missing 'name' field"
        assert fm["name"] == "mux-ospec", f"Expected name 'mux-ospec', got '{fm['name']}'"

    def test_description_field_exists(self) -> None:
        """Frontmatter must have 'description' field."""
        fm = self._parse_frontmatter()
        assert "description" in fm, "frontmatter missing 'description' field"
        assert len(fm["description"]) > 20, "description too short"

    def test_project_agnostic_field(self) -> None:
        """Frontmatter should declare project-agnostic status."""
        fm = self._parse_frontmatter()
        assert "project-agnostic" in fm, "frontmatter missing 'project-agnostic' field"
        assert fm["project-agnostic"] is True, "mux-ospec should be project-agnostic"

    def test_allowed_tools_field(self) -> None:
        """Frontmatter must list allowed tools."""
        fm = self._parse_frontmatter()
        assert "allowed-tools" in fm, "frontmatter missing 'allowed-tools' field"

        tools = fm["allowed-tools"]
        assert isinstance(tools, list), "allowed-tools must be a list"

        # Required tools for orchestrator
        assert "Task" in tools, "Task tool required for delegation"
        assert "Bash" in tools, "Bash tool required for signal/session tools"

    def test_no_file_operation_tools(self) -> None:
        """Orchestrator must not have direct file operation tools."""
        fm = self._parse_frontmatter()
        tools = fm.get("allowed-tools", [])

        forbidden = ["Read", "Write", "Edit", "Grep", "Glob"]
        for tool in forbidden:
            assert tool not in tools, f"{tool} is forbidden - orchestrators delegate file operations"


class TestToolScripts:
    """Validate tool scripts."""

    def test_detect_repo_type_exists(self) -> None:
        """detect-repo-type.py tool must exist."""
        tool = SKILL_ROOT / "tools" / "detect-repo-type.py"
        assert tool.exists(), "detect-repo-type.py not found"

    def test_detect_repo_type_is_executable(self) -> None:
        """Tool script should have executable permission."""
        tool = SKILL_ROOT / "tools" / "detect-repo-type.py"
        # Check if file has executable bit or starts with shebang
        content = tool.read_text()
        assert content.startswith("#!/usr/bin/env python3"), "Tool must have shebang"

    def test_detect_repo_type_has_pep723_deps(self) -> None:
        """Tool should have PEP 723 inline dependencies."""
        tool = SKILL_ROOT / "tools" / "detect-repo-type.py"
        content = tool.read_text()

        assert "# /// script" in content, "Tool should have PEP 723 script block"
        assert "# requires-python" in content, "Tool should specify Python version"


class TestAgentDefinitions:
    """Validate agent markdown definitions."""

    def _get_agent_files(self) -> list[Path]:
        """Get all agent .md files."""
        agents_dir = SKILL_ROOT / "agents"
        return list(agents_dir.glob("*.md"))

    def test_agents_exist(self) -> None:
        """At least one agent definition must exist."""
        agents = self._get_agent_files()
        assert len(agents) > 0, "No agent definitions found"

    def test_expected_agents_present(self) -> None:
        """Expected agent files should be present."""
        agents_dir = SKILL_ROOT / "agents"

        # These agents are documented in SKILL.md
        expected = [
            "spec-analyzer.md",  # or similar
            "phase-executor.md",
            "validator.md",
        ]

        found = [f.name for f in agents_dir.glob("*.md")]

        for agent in expected:
            # Allow partial matches (spec-analyzer vs spec_analyzer)
            base = agent.replace(".md", "").replace("-", "_")
            matched = any(base in f.replace("-", "_") for f in found)
            assert matched, f"Expected agent '{agent}' not found in {found}"

    def test_agent_files_not_empty(self) -> None:
        """Agent files must have content."""
        for agent in self._get_agent_files():
            content = agent.read_text()
            assert len(content) > 50, f"Agent {agent.name} appears empty"


class TestSignalProtocolCompliance:
    """Validate signal protocol is properly documented."""

    def test_skill_md_documents_signal_protocol(self) -> None:
        """SKILL.md must document signal protocol."""
        skill_md = SKILL_ROOT / "SKILL.md"
        content = skill_md.read_text()

        assert "signal" in content.lower(), "SKILL.md should mention signals"
        assert ".signals/" in content or ".signals" in content, "SKILL.md should document .signals directory"

    def test_skill_md_documents_phases(self) -> None:
        """SKILL.md must document phase workflow."""
        skill_md = SKILL_ROOT / "SKILL.md"
        content = skill_md.read_text()

        # Key phases that must be documented
        required_concepts = ["GATHER", "IMPLEMENT", "REVIEW", "TEST"]

        for concept in required_concepts:
            assert concept in content, f"SKILL.md should document {concept} phase"


class TestCompositionRequirements:
    """Validate mux-ospec composes with required skills."""

    def test_skill_md_references_mux(self) -> None:
        """SKILL.md must reference /mux skill for parallel research."""
        skill_md = SKILL_ROOT / "SKILL.md"
        content = skill_md.read_text()

        assert "/mux" in content or "mux" in content.lower(), "SKILL.md should reference /mux skill"

    def test_skill_md_references_spec(self) -> None:
        """SKILL.md must reference /spec skill for stage execution."""
        skill_md = SKILL_ROOT / "SKILL.md"
        content = skill_md.read_text()

        assert "/spec" in content or 'skill="spec"' in content, "SKILL.md should reference /spec skill"

    def test_no_direct_skill_invocation(self) -> None:
        """SKILL.md should delegate Skill() via Task(), not call directly."""
        skill_md = SKILL_ROOT / "SKILL.md"
        content = skill_md.read_text()

        # Should use Task(prompt="...Skill(...)...") pattern
        assert "Task(" in content, "Should delegate via Task()"
        # Direct Skill() forbidden is documented
        assert "Direct Skill()" in content or "NEVER invoke Skill() directly" in content, \
            "Should document direct Skill() prohibition"
