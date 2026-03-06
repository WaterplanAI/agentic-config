"""Unit tests for Phase 3 template system: loading, validation, CLI integration."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (
    load_template,
    merge_config,
    resolve_layer_config,
    validate_template_bundle,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "config" / "templates"
CAMPAIGN_SCRIPT = Path(__file__).resolve().parent.parent / "campaign.py"

EXPECTED_TEMPLATES = [
    "big-feature",
    "iteration",
    "planning-only",
    "debug-fix",
    "research-only",
    "chores",
]


# -- Template validation tests --


def test_all_templates_exist() -> None:
    """All 6 template files must exist."""
    for name in EXPECTED_TEMPLATES:
        path = TEMPLATES_DIR / f"{name}.json"
        assert path.is_file(), f"Template missing: {path}"


def test_all_templates_valid_json() -> None:
    """All templates must parse as valid JSON."""
    for name in EXPECTED_TEMPLATES:
        path = TEMPLATES_DIR / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{name}: root must be dict"


def test_all_templates_pass_validation_without_warnings() -> None:
    """All templates must pass validate_template_bundle() with zero warnings."""
    for name in EXPECTED_TEMPLATES:
        path = TEMPLATES_DIR / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        warnings = validate_template_bundle(data)
        assert warnings == [], f"{name}: unexpected warnings: {warnings}"


def test_all_templates_have_required_fields() -> None:
    """All templates must have template_name, template_version, description, layers."""
    for name in EXPECTED_TEMPLATES:
        path = TEMPLATES_DIR / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "template_name" in data, f"{name}: missing template_name"
        assert "template_version" in data, f"{name}: missing template_version"
        assert "description" in data, f"{name}: missing description"
        assert "layers" in data, f"{name}: missing layers"
        assert data["template_name"] == name, f"{name}: template_name mismatch"


def test_all_templates_have_l4_layer() -> None:
    """All templates must have an L4 layer with the 4 campaign sections."""
    for name in EXPECTED_TEMPLATES:
        path = TEMPLATES_DIR / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        l4 = data.get("layers", {}).get("L4", {})
        for section in ("research", "planning", "execution", "validation"):
            assert section in l4, f"{name}: L4 missing '{section}' section"


# -- load_template tests --


def test_load_template_by_name() -> None:
    """load_template('big-feature') should load from templates dir."""
    script_dir = Path(__file__).resolve().parent.parent
    template = load_template("big-feature", script_dir)
    assert template["template_name"] == "big-feature"


def test_load_template_by_path() -> None:
    """load_template with .json path should load directly."""
    path = str(TEMPLATES_DIR / "iteration.json")
    template = load_template(path)
    assert template["template_name"] == "iteration"


def test_load_template_not_found() -> None:
    """load_template with invalid name should raise FileNotFoundError."""
    try:
        load_template("nonexistent-template-xyz")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


# -- resolve_layer_config tests --


def test_resolve_l4_from_template() -> None:
    """resolve_layer_config extracts L4 section."""
    script_dir = Path(__file__).resolve().parent.parent
    template = load_template("big-feature", script_dir)
    l4 = resolve_layer_config(template, "L4")
    assert l4["research"]["enabled"] is True
    assert l4["validation"]["max_heal_cycles"] == 2


def test_resolve_l1_sub_key() -> None:
    """resolve_layer_config with sub_key extracts nested section."""
    script_dir = Path(__file__).resolve().parent.parent
    template = load_template("big-feature", script_dir)
    spec_config = resolve_layer_config(template, "L1", "spec")
    assert "stage_model_defaults" in spec_config


def test_resolve_missing_layer_returns_empty() -> None:
    """resolve_layer_config for missing layer returns empty dict."""
    template = {"layers": {"L4": {"research": {"enabled": True}}}}
    result = resolve_layer_config(template, "L1")
    assert result == {}


# -- CLI overlay precedence tests --


def test_cli_overlay_overrides_template() -> None:
    """CLI args should override template values when merged."""
    from lib import resolve_campaign_config
    import argparse

    script_dir = Path(__file__).resolve().parent.parent
    template = load_template("chores", script_dir)
    l4 = resolve_layer_config(template, "L4")

    # chores has max_depth=3, override with CLI
    base = {
        "research": {"enabled": True, "domains": ["market", "ux", "tech"], "max_rounds": 3},
        "planning": {"enabled": True},
        "execution": {"enabled": True, "max_depth": 5},
        "validation": {"enabled": True, "max_heal_cycles": 2},
    }
    config = merge_config(base, l4)
    ns = argparse.Namespace(max_depth=7, max_research_rounds=None, max_heal_cycles=None)
    resolved = resolve_campaign_config(config, ns)
    assert resolved["execution"]["max_depth"] == 7, "CLI should override template"


def test_backward_compat_no_template() -> None:
    """Without --template, config should equal defaults + CLI overrides."""
    from campaign import get_default_config
    from lib import resolve_campaign_config
    import argparse

    config = get_default_config()
    ns = argparse.Namespace(max_depth=None, max_research_rounds=None, max_heal_cycles=None)
    resolved = resolve_campaign_config(config, ns)
    # Should match defaults exactly
    assert resolved["research"]["max_rounds"] == 3
    assert resolved["execution"]["max_depth"] == 5
    assert resolved["validation"]["max_heal_cycles"] == 2


# -- Template-specific behavior tests --


def test_iteration_disables_research_and_planning() -> None:
    """iteration template should have research and planning disabled."""
    script_dir = Path(__file__).resolve().parent.parent
    template = load_template("iteration", script_dir)
    l4 = resolve_layer_config(template, "L4")
    assert l4["research"]["enabled"] is False
    assert l4["planning"]["enabled"] is False
    assert l4["execution"]["enabled"] is True
    assert l4["validation"]["enabled"] is False


def test_planning_only_disables_execution() -> None:
    """planning-only template should disable execution and validation."""
    script_dir = Path(__file__).resolve().parent.parent
    template = load_template("planning-only", script_dir)
    l4 = resolve_layer_config(template, "L4")
    assert l4["research"]["enabled"] is True
    assert l4["planning"]["enabled"] is True
    assert l4["execution"]["enabled"] is False
    assert l4["validation"]["enabled"] is False


def test_debug_fix_has_one_heal_cycle() -> None:
    """debug-fix template should have validation enabled with 1 heal cycle."""
    script_dir = Path(__file__).resolve().parent.parent
    template = load_template("debug-fix", script_dir)
    l4 = resolve_layer_config(template, "L4")
    assert l4["validation"]["enabled"] is True
    assert l4["validation"]["max_heal_cycles"] == 1


def test_research_only_all_high_tier() -> None:
    """research-only should use high-tier for research model and consolidation."""
    script_dir = Path(__file__).resolve().parent.parent
    template = load_template("research-only", script_dir)
    l4 = resolve_layer_config(template, "L4")
    assert l4["research"]["model"] == "high-tier"
    assert l4["research"]["consolidation_model"] == "high-tier"


def test_chores_uses_low_tier() -> None:
    """chores should use low-tier for research."""
    script_dir = Path(__file__).resolve().parent.parent
    template = load_template("chores", script_dir)
    l4 = resolve_layer_config(template, "L4")
    assert l4["research"]["model"] == "low-tier"
    assert l4["research"]["consolidation_model"] == "low-tier"


# -- Dry-run and list-templates CLI tests --


def test_dry_run_outputs_json() -> None:
    """--dry-run should output valid JSON to stdout."""
    result = subprocess.run(
        ["uv", "run", str(CAMPAIGN_SCRIPT), "--topic", "test", "--template", "chores", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"dry-run failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert "research" in data
    assert "execution" in data


def test_list_templates_outputs_all_six() -> None:
    """--list-templates should list all 6 templates."""
    result = subprocess.run(
        ["uv", "run", str(CAMPAIGN_SCRIPT), "--topic", "x", "--list-templates"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"list-templates failed: {result.stderr}"
    for name in EXPECTED_TEMPLATES:
        assert name in result.stdout, f"Missing template in output: {name}"


if __name__ == "__main__":
    import traceback

    test_functions = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for fn in test_functions:
        try:
            fn()
            passed += 1
            print(f"  PASS: {fn.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL: {fn.__name__}")
            traceback.print_exc()
    print(f"\nResults: {passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(1 if failed else 0)
