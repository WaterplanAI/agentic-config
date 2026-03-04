"""Unit tests for campaign config loading, validation, merge, and resolve."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (
    load_campaign_config,
    merge_config,
    resolve_campaign_config,
    validate_campaign_config,
)


# -- validate_campaign_config tests --


def test_valid_config_no_warnings() -> None:
    """Valid config should produce zero warnings."""
    config = {
        "research": {
            "enabled": True,
            "domains": ["market", "ux", "tech"],
            "max_rounds": 3,
            "model": "medium-tier",
            "consolidation_model": "high-tier",
            "timeout_per_worker": 300,
            "timeout_overall": 600,
        },
        "planning": {
            "enabled": True,
            "roadmap_model": "high-tier",
            "decompose_model": "medium-tier",
            "ceo_review": True,
        },
        "execution": {
            "enabled": True,
            "max_depth": 5,
            "timeout": 3600,
        },
        "validation": {
            "enabled": True,
            "evaluator_model": "medium-tier",
            "max_heal_cycles": 2,
        },
    }
    warnings = validate_campaign_config(config)
    assert warnings == [], f"Expected no warnings, got: {warnings}"


def test_unknown_toplevel_key_warns() -> None:
    """Unknown top-level keys produce warnings, not errors."""
    config = {"research": {"enabled": True}, "future_feature": {}}
    warnings = validate_campaign_config(config)
    assert any("Unknown top-level key" in w for w in warnings), f"Missing unknown key warning: {warnings}"


def test_unknown_nested_key_warns() -> None:
    """Unknown nested keys produce warnings."""
    config = {"research": {"enabled": True, "unknown_field": 42}}
    warnings = validate_campaign_config(config)
    assert any("Unknown key research.unknown_field" in w for w in warnings), f"Missing nested key warning: {warnings}"


def test_max_rounds_out_of_range() -> None:
    """max_rounds outside 1-5 should warn."""
    config = {"research": {"max_rounds": 10}}
    warnings = validate_campaign_config(config)
    assert any("max_rounds" in w for w in warnings), f"Missing range warning: {warnings}"


def test_max_rounds_zero() -> None:
    """max_rounds = 0 should warn (minimum is 1)."""
    config = {"research": {"max_rounds": 0}}
    warnings = validate_campaign_config(config)
    assert any("max_rounds" in w for w in warnings)


def test_max_depth_below_minimum() -> None:
    """max_depth < 3 should warn."""
    config = {"execution": {"max_depth": 1}}
    warnings = validate_campaign_config(config)
    assert any("max_depth" in w for w in warnings)


def test_timeout_overall_less_than_per_worker() -> None:
    """timeout_overall < timeout_per_worker should warn."""
    config = {"research": {"timeout_per_worker": 300, "timeout_overall": 100}}
    warnings = validate_campaign_config(config)
    assert any("timeout_overall must be >= timeout_per_worker" in w for w in warnings)


def test_invalid_model_tier() -> None:
    """Invalid model tier should warn."""
    config = {"research": {"model": "super-mega-tier"}}
    warnings = validate_campaign_config(config)
    assert any("model" in w and "tier name" in w for w in warnings)


def test_claude_model_id_accepted() -> None:
    """claude-* model IDs should be accepted without warning."""
    config = {"research": {"model": "claude-sonnet-4-20250514"}}
    warnings = validate_campaign_config(config)
    assert not any("model" in w for w in warnings), f"Unexpected model warning: {warnings}"


def test_enabled_non_bool_warns() -> None:
    """enabled as non-bool should warn."""
    config = {"research": {"enabled": "yes"}}
    warnings = validate_campaign_config(config)
    assert any("enabled" in w and "bool" in w for w in warnings)


def test_heal_cycles_out_of_range() -> None:
    """max_heal_cycles > 5 should warn."""
    config = {"validation": {"max_heal_cycles": 10}}
    warnings = validate_campaign_config(config)
    assert any("max_heal_cycles" in w for w in warnings)


def test_empty_config_valid() -> None:
    """Empty config should produce no warnings."""
    assert validate_campaign_config({}) == []


# -- load_campaign_config tests --


def test_load_valid_config() -> None:
    """Loading a valid JSON config should return dict."""
    config_data = {"research": {"max_rounds": 2}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        f.flush()
        result = load_campaign_config(Path(f.name))
    assert result == config_data


def test_load_missing_file() -> None:
    """Loading a missing file should raise FileNotFoundError."""
    try:
        load_campaign_config(Path("/nonexistent/config.json"))
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


def test_load_invalid_json() -> None:
    """Loading invalid JSON should raise JSONDecodeError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not valid json {{{")
        f.flush()
        try:
            load_campaign_config(Path(f.name))
            assert False, "Should have raised JSONDecodeError"
        except json.JSONDecodeError:
            pass


# -- merge_config tests --


def test_merge_nested_dicts() -> None:
    """Nested dicts should merge recursively."""
    base = {"research": {"max_rounds": 3, "domains": ["market"]}}
    override = {"research": {"max_rounds": 5}}
    result = merge_config(base, override)
    assert result == {"research": {"max_rounds": 5, "domains": ["market"]}}


def test_merge_override_replaces_lists() -> None:
    """Lists in override should replace, not merge."""
    base = {"research": {"domains": ["market", "ux"]}}
    override = {"research": {"domains": ["tech"]}}
    result = merge_config(base, override)
    assert result["research"]["domains"] == ["tech"]


def test_merge_preserves_base_keys() -> None:
    """Base keys not in override should be preserved."""
    base = {"research": {"max_rounds": 3}, "planning": {"enabled": True}}
    override = {"research": {"max_rounds": 1}}
    result = merge_config(base, override)
    assert result["planning"]["enabled"] is True


# -- resolve_campaign_config tests --


def test_resolve_maps_three_args() -> None:
    """resolve should map 3 CLI args into config structure."""
    ns = argparse.Namespace(max_depth=7, max_research_rounds=2, max_heal_cycles=1)
    config: dict = {"execution": {}, "research": {}, "validation": {}}
    result = resolve_campaign_config(config, ns)
    assert result["execution"]["max_depth"] == 7
    assert result["research"]["max_rounds"] == 2
    assert result["validation"]["max_heal_cycles"] == 1


def test_resolve_creates_missing_sections() -> None:
    """resolve should create sections if not present."""
    ns = argparse.Namespace(max_depth=4, max_research_rounds=None, max_heal_cycles=None)
    config: dict = {}
    result = resolve_campaign_config(config, ns)
    assert result["execution"]["max_depth"] == 4
    assert "research" not in result  # Not set because CLI arg was None


def test_resolve_none_args_dont_override() -> None:
    """None CLI args should not override config values."""
    ns = argparse.Namespace(max_depth=None, max_research_rounds=None, max_heal_cycles=None)
    config = {"execution": {"max_depth": 10}}
    result = resolve_campaign_config(config, ns)
    assert result["execution"]["max_depth"] == 10


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
