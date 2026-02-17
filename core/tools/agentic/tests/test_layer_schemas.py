"""Unit tests for L0-L3 layer config validators, template bundle, and helpers."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (
    VALID_PERMISSION_MODES,
    _check_bool_field,
    _check_enum,
    _check_int_range,
    _check_model,
    _check_nullable_str,
    _check_str,
    _check_type,
    load_template,
    resolve_layer_config,
    validate_l0_config,
    validate_l1_config,
    validate_l2_ospec_config,
    validate_l2_oresearch_config,
    validate_l3_config,
    validate_template_bundle,
)


# ============================================================================
# Shared helper tests
# ============================================================================


class TestCheckType:
    def test_correct_type(self) -> None:
        w: list[str] = []
        assert _check_type(w, "x", "hello", str) is True
        assert w == []

    def test_wrong_type(self) -> None:
        w: list[str] = []
        assert _check_type(w, "x", 42, str) is False
        assert len(w) == 1 and "str" in w[0]

    def test_bool_rejected_as_int(self) -> None:
        w: list[str] = []
        assert _check_type(w, "x", True, int) is False
        assert len(w) == 1 and "bool" in w[0]


class TestCheckStr:
    def test_valid(self) -> None:
        w: list[str] = []
        _check_str(w, "x", "hello")
        assert w == []

    def test_empty_rejected(self) -> None:
        w: list[str] = []
        _check_str(w, "x", "")
        assert len(w) == 1 and "non-empty" in w[0]

    def test_empty_allowed(self) -> None:
        w: list[str] = []
        _check_str(w, "x", "", allow_empty=True)
        assert w == []

    def test_non_string(self) -> None:
        w: list[str] = []
        _check_str(w, "x", 42)
        assert len(w) == 1


class TestCheckIntRange:
    def test_in_range(self) -> None:
        w: list[str] = []
        _check_int_range(w, "x", 5, 1, 10)
        assert w == []

    def test_below_range(self) -> None:
        w: list[str] = []
        _check_int_range(w, "x", 0, 1, 10)
        assert len(w) == 1 and "1-10" in w[0]

    def test_above_range(self) -> None:
        w: list[str] = []
        _check_int_range(w, "x", 11, 1, 10)
        assert len(w) == 1

    def test_non_int(self) -> None:
        w: list[str] = []
        _check_int_range(w, "x", "5", 1, 10)
        assert len(w) == 1


class TestCheckModel:
    def test_valid_tier(self) -> None:
        w: list[str] = []
        _check_model(w, "x", "medium-tier")
        assert w == []

    def test_claude_id(self) -> None:
        w: list[str] = []
        _check_model(w, "x", "claude-sonnet-4-20250514")
        assert w == []

    def test_invalid(self) -> None:
        w: list[str] = []
        _check_model(w, "x", "bad-model")
        assert len(w) == 1 and "tier name" in w[0]


class TestCheckBoolField:
    def test_valid(self) -> None:
        w: list[str] = []
        _check_bool_field(w, "x", True)
        assert w == []

    def test_invalid(self) -> None:
        w: list[str] = []
        _check_bool_field(w, "x", "yes")
        assert len(w) == 1 and "bool" in w[0]


class TestCheckEnum:
    def test_valid(self) -> None:
        w: list[str] = []
        _check_enum(w, "x", "acceptEdits", VALID_PERMISSION_MODES)
        assert w == []

    def test_invalid(self) -> None:
        w: list[str] = []
        _check_enum(w, "x", "invalid", VALID_PERMISSION_MODES)
        assert len(w) == 1 and "must be one of" in w[0]


class TestCheckNullableStr:
    def test_null(self) -> None:
        w: list[str] = []
        _check_nullable_str(w, "x", None)
        assert w == []

    def test_string(self) -> None:
        w: list[str] = []
        _check_nullable_str(w, "x", "hello")
        assert w == []

    def test_non_string(self) -> None:
        w: list[str] = []
        _check_nullable_str(w, "x", 42)
        assert len(w) == 1


# ============================================================================
# L0 spawn config tests
# ============================================================================


class TestValidateL0Config:
    def test_valid_config(self) -> None:
        config = {
            "model": "medium-tier",
            "max_depth": 3,
            "output_format": "text",
            "permission_mode": "acceptEdits",
            "allowed_tools": None,
            "system_prompt": None,
            "cwd": None,
            "session_dir": None,
            "signal_name": None,
            "trace_id": None,
            "current_depth": None,
        }
        assert validate_l0_config(config) == []

    def test_empty_config(self) -> None:
        assert validate_l0_config({}) == []

    def test_unknown_key(self) -> None:
        w = validate_l0_config({"future_field": 1})
        assert any("Unknown L0 key" in x for x in w)

    def test_invalid_model(self) -> None:
        w = validate_l0_config({"model": "bad"})
        assert any("tier name" in x for x in w)

    def test_max_depth_out_of_range(self) -> None:
        w = validate_l0_config({"max_depth": 0})
        assert any("1-10" in x for x in w)
        w = validate_l0_config({"max_depth": 11})
        assert any("1-10" in x for x in w)

    def test_invalid_permission_mode(self) -> None:
        w = validate_l0_config({"permission_mode": "invalid"})
        assert any("must be one of" in x for x in w)

    def test_allowed_tools_valid_list(self) -> None:
        w = validate_l0_config({"allowed_tools": ["Bash", "Read"]})
        assert w == []

    def test_allowed_tools_invalid_item(self) -> None:
        w = validate_l0_config({"allowed_tools": ["Bash", 42]})
        assert any("non-empty string" in x for x in w)

    def test_allowed_tools_null(self) -> None:
        assert validate_l0_config({"allowed_tools": None}) == []

    def test_allowed_tools_wrong_type(self) -> None:
        w = validate_l0_config({"allowed_tools": "Bash"})
        assert any("list of strings or null" in x for x in w)


# ============================================================================
# L1 executor config tests
# ============================================================================


class TestValidateL1Config:
    def test_valid_config(self) -> None:
        config = {
            "model": "medium-tier",
            "max_depth": 3,
            "output_format": "text",
            "cwd": None,
            "enabled": True,
            "stage_model_defaults": {
                "RESEARCH": "medium-tier",
                "PLAN": "medium-tier",
                "IMPLEMENT": "high-tier",
            },
        }
        assert validate_l1_config(config) == []

    def test_empty_config(self) -> None:
        assert validate_l1_config({}) == []

    def test_unknown_key(self) -> None:
        w = validate_l1_config({"future": 1})
        assert any("Unknown L1 key" in x for x in w)

    def test_invalid_model_in_stage_defaults(self) -> None:
        w = validate_l1_config({"stage_model_defaults": {"PLAN": "bad"}})
        assert any("tier name" in x for x in w)

    def test_stage_defaults_not_dict(self) -> None:
        w = validate_l1_config({"stage_model_defaults": "string"})
        assert any("must be dict" in x for x in w)

    def test_enabled_non_bool(self) -> None:
        w = validate_l1_config({"enabled": "yes"})
        assert any("bool" in x for x in w)


# ============================================================================
# L2 ospec config tests
# ============================================================================


class TestValidateL2OspecConfig:
    def test_valid_config(self) -> None:
        config = {
            "executor": "core/tools/agentic/spec.py",
            "modifier": "full",
            "stages": [
                {
                    "name": "RESEARCH",
                    "model": "medium-tier",
                    "retry": 1,
                    "required": True,
                    "timeout": 600,
                },
                {"name": "PLAN", "model": "medium-tier", "retry": 1, "required": True},
                {
                    "name": "IMPLEMENT",
                    "model": "high-tier",
                    "retry": 1,
                    "required": True,
                },
            ],
            "session_dir": None,
            "max_depth": 3,
            "cwd": None,
        }
        assert validate_l2_ospec_config(config) == []

    def test_empty_config(self) -> None:
        assert validate_l2_ospec_config({}) == []

    def test_unknown_key(self) -> None:
        w = validate_l2_ospec_config({"future": 1})
        assert any("Unknown L2-ospec key" in x for x in w)

    def test_invalid_stage_name(self) -> None:
        w = validate_l2_ospec_config({"stages": [{"name": "INVALID"}]})
        assert any("must be one of" in x for x in w)

    def test_stage_retry_out_of_range(self) -> None:
        w = validate_l2_ospec_config({"stages": [{"name": "RESEARCH", "retry": 99}]})
        assert any("0-5" in x for x in w)

    def test_stage_timeout_out_of_range(self) -> None:
        w = validate_l2_ospec_config({"stages": [{"name": "RESEARCH", "timeout": 10}]})
        assert any("60-3600" in x for x in w)

    def test_stage_required_non_bool(self) -> None:
        w = validate_l2_ospec_config(
            {"stages": [{"name": "RESEARCH", "required": "yes"}]}
        )
        assert any("bool" in x for x in w)

    def test_stages_not_list(self) -> None:
        w = validate_l2_ospec_config({"stages": "invalid"})
        assert any("must be list" in x for x in w)

    def test_unknown_stage_key(self) -> None:
        w = validate_l2_ospec_config({"stages": [{"name": "RESEARCH", "future": 1}]})
        assert any("will be ignored" in x for x in w)


# ============================================================================
# L2 oresearch config tests
# ============================================================================


class TestValidateL2OresearchConfig:
    def test_valid_config(self) -> None:
        config = {
            "executor": "core/tools/agentic/researcher.py",
            "workers": [
                {
                    "domain": "market",
                    "model": "medium-tier",
                    "focus": "competitive analysis",
                    "enabled": True,
                },
                {"domain": "ux", "model": "medium-tier"},
            ],
            "consolidation_model": "high-tier",
            "timeout_per_worker": 300,
            "timeout_overall": 600,
            "max_concurrency": 4,
            "session_dir": None,
            "max_depth": 3,
            "round_number": 1,
        }
        assert validate_l2_oresearch_config(config) == []

    def test_empty_config(self) -> None:
        assert validate_l2_oresearch_config({}) == []

    def test_unknown_key(self) -> None:
        w = validate_l2_oresearch_config({"future": 1})
        assert any("Unknown L2-oresearch key" in x for x in w)

    def test_timeout_overall_less_than_per_worker(self) -> None:
        w = validate_l2_oresearch_config(
            {"timeout_per_worker": 300, "timeout_overall": 100}
        )
        assert any("timeout_overall must be >= timeout_per_worker" in x for x in w)

    def test_max_concurrency_out_of_range(self) -> None:
        w = validate_l2_oresearch_config({"max_concurrency": 0})
        assert any("1-8" in x for x in w)
        w = validate_l2_oresearch_config({"max_concurrency": 10})
        assert any("1-8" in x for x in w)

    def test_duplicate_worker_domain(self) -> None:
        w = validate_l2_oresearch_config(
            {
                "workers": [
                    {"domain": "market", "model": "medium-tier"},
                    {"domain": "market", "model": "high-tier"},
                ]
            }
        )
        assert any("duplicate" in x for x in w)

    def test_worker_focus_null(self) -> None:
        w = validate_l2_oresearch_config(
            {"workers": [{"domain": "market", "focus": None}]}
        )
        assert w == [] or not any("focus" in x for x in w)

    def test_worker_enabled_non_bool(self) -> None:
        w = validate_l2_oresearch_config(
            {"workers": [{"domain": "market", "enabled": "yes"}]}
        )
        assert any("bool" in x for x in w)

    def test_workers_not_list(self) -> None:
        w = validate_l2_oresearch_config({"workers": "invalid"})
        assert any("must be list" in x for x in w)


# ============================================================================
# L3 coordinator config tests
# ============================================================================


class TestValidateL3Config:
    def test_valid_config(self) -> None:
        config = {
            "name": "coordinator-name",
            "description": "Phase coordination config",
            "phases": [
                {
                    "name": "phase-01-research",
                    "orchestrator": "core/tools/agentic/ospec.py",
                    "modifier": "full",
                    "target": "specs/example/001-feature.md",
                    "depends_on": [],
                    "retry": 1,
                    "timeout": 1800,
                    "required": True,
                },
                {
                    "name": "phase-02-implement",
                    "orchestrator": "core/tools/agentic/ospec.py",
                    "modifier": "leanest",
                    "target": "specs/example/002-tests.md",
                    "depends_on": ["phase-01-research"],
                    "retry": 0,
                    "timeout": 3600,
                    "required": True,
                },
            ],
            "max_depth": 5,
            "cwd": None,
            "session_dir": None,
            "checkpoint_enabled": True,
        }
        assert validate_l3_config(config) == []

    def test_empty_config(self) -> None:
        assert validate_l3_config({}) == []

    def test_unknown_key(self) -> None:
        w = validate_l3_config({"future": 1})
        assert any("Unknown L3 key" in x for x in w)

    def test_dag_forward_reference(self) -> None:
        """depends_on referencing a phase not yet seen produces warning."""
        config = {
            "phases": [
                {"name": "p1", "orchestrator": "x.py", "depends_on": ["p2"]},
                {"name": "p2", "orchestrator": "x.py"},
            ]
        }
        w = validate_l3_config(config)
        assert any("does not appear earlier" in x for x in w)

    def test_dag_self_reference(self) -> None:
        """depends_on self-referencing produces warning."""
        config = {
            "phases": [
                {"name": "p1", "orchestrator": "x.py", "depends_on": ["p1"]},
            ]
        }
        w = validate_l3_config(config)
        assert any("self-references" in x for x in w)

    def test_duplicate_phase_name(self) -> None:
        config = {
            "phases": [
                {"name": "p1", "orchestrator": "x.py"},
                {"name": "p1", "orchestrator": "y.py"},
            ]
        }
        w = validate_l3_config(config)
        assert any("duplicate" in x for x in w)

    def test_phase_timeout_out_of_range(self) -> None:
        config = {"phases": [{"name": "p1", "orchestrator": "x.py", "timeout": 100}]}
        w = validate_l3_config(config)
        assert any("300-7200" in x for x in w)

    def test_phase_retry_out_of_range(self) -> None:
        config = {"phases": [{"name": "p1", "orchestrator": "x.py", "retry": 10}]}
        w = validate_l3_config(config)
        assert any("0-5" in x for x in w)

    def test_phase_missing_name(self) -> None:
        config = {"phases": [{"orchestrator": "x.py"}]}
        w = validate_l3_config(config)
        assert any("name is required" in x for x in w)

    def test_checkpoint_non_bool(self) -> None:
        w = validate_l3_config({"checkpoint_enabled": "yes"})
        assert any("bool" in x for x in w)

    def test_phases_not_list(self) -> None:
        w = validate_l3_config({"phases": "invalid"})
        assert any("must be list" in x for x in w)

    def test_valid_dag_ordering(self) -> None:
        """Valid backward references produce no warnings."""
        config = {
            "phases": [
                {"name": "p1", "orchestrator": "x.py", "depends_on": []},
                {"name": "p2", "orchestrator": "x.py", "depends_on": ["p1"]},
                {"name": "p3", "orchestrator": "x.py", "depends_on": ["p1", "p2"]},
            ]
        }
        assert validate_l3_config(config) == []


# ============================================================================
# Template bundle tests
# ============================================================================


class TestValidateTemplateBundle:
    def test_valid_minimal(self) -> None:
        config = {
            "template_name": "big-feature",
            "template_version": "1.0",
        }
        assert validate_template_bundle(config) == []

    def test_missing_template_name(self) -> None:
        w = validate_template_bundle({"template_version": "1.0"})
        assert any("template_name is required" in x for x in w)

    def test_invalid_version_format(self) -> None:
        w = validate_template_bundle({"template_name": "x", "template_version": "abc"})
        assert any("must match" in x for x in w)

    def test_valid_version(self) -> None:
        w = validate_template_bundle({"template_name": "x", "template_version": "2.1"})
        assert not any("version" in x for x in w)

    def test_unknown_key(self) -> None:
        w = validate_template_bundle({"template_name": "x", "future": 1})
        assert any("Unknown template key" in x for x in w)

    def test_unknown_layer_key(self) -> None:
        w = validate_template_bundle({"template_name": "x", "layers": {"L9": {}}})
        assert any("Unknown template.layers key" in x for x in w)

    def test_l4_delegated_to_campaign_validator(self) -> None:
        """L4 should be validated by validate_campaign_config."""
        config = {
            "template_name": "x",
            "template_version": "1.0",
            "layers": {"L4": {"research": {"model": "bad-model"}}},
        }
        w = validate_template_bundle(config)
        assert any("tier name" in x for x in w)

    def test_l0_in_layers(self) -> None:
        config = {
            "template_name": "x",
            "template_version": "1.0",
            "layers": {"L0": {"model": "medium-tier", "max_depth": 3}},
        }
        assert validate_template_bundle(config) == []

    def test_l2_sub_keys(self) -> None:
        config = {
            "template_name": "x",
            "template_version": "1.0",
            "layers": {
                "L2": {
                    "ospec": {"executor": "spec.py"},
                    "oresearch": {"executor": "researcher.py"},
                }
            },
        }
        assert validate_template_bundle(config) == []

    def test_l1_sub_keys(self) -> None:
        config = {
            "template_name": "x",
            "template_version": "1.0",
            "layers": {
                "L1": {
                    "spec": {"model": "medium-tier"},
                    "researcher": {"model": "medium-tier"},
                }
            },
        }
        assert validate_template_bundle(config) == []

    def test_full_valid_template(self) -> None:
        config = {
            "$schema": "https://agentic-config/schemas/template-v1.json",
            "template_name": "big-feature",
            "template_version": "1.0",
            "description": "Full pipeline",
            "min_stack_version": "0.16.0",
            "layers": {
                "L0": {"model": "medium-tier"},
                "L1": {"spec": {"enabled": True}, "researcher": {"enabled": True}},
                "L2": {
                    "ospec": {"executor": "spec.py"},
                    "oresearch": {"executor": "researcher.py"},
                },
                "L3": {
                    "name": "coord",
                    "phases": [{"name": "p1", "orchestrator": "x.py"}],
                },
                "L4": {"research": {"enabled": True}},
            },
        }
        assert validate_template_bundle(config) == []


# ============================================================================
# resolve_layer_config tests
# ============================================================================


class TestResolveLayerConfig:
    def test_resolve_l0(self) -> None:
        template = {"layers": {"L0": {"model": "high-tier"}}}
        result = resolve_layer_config(template, "L0")
        assert result == {"model": "high-tier"}

    def test_resolve_l1_sub_key(self) -> None:
        template = {"layers": {"L1": {"spec": {"enabled": True}}}}
        result = resolve_layer_config(template, "L1", sub_key="spec")
        assert result == {"enabled": True}

    def test_resolve_l2_sub_key(self) -> None:
        template = {"layers": {"L2": {"ospec": {"executor": "spec.py"}}}}
        result = resolve_layer_config(template, "L2", sub_key="ospec")
        assert result == {"executor": "spec.py"}

    def test_resolve_missing_layer(self) -> None:
        template = {"layers": {}}
        result = resolve_layer_config(template, "L0")
        assert result == {}

    def test_resolve_missing_sub_key(self) -> None:
        template = {"layers": {"L1": {"spec": {"enabled": True}}}}
        result = resolve_layer_config(template, "L1", sub_key="researcher")
        assert result == {}

    def test_resolve_no_layers(self) -> None:
        template = {}
        result = resolve_layer_config(template, "L0")
        assert result == {}


# ============================================================================
# load_template tests
# ============================================================================


class TestLoadTemplate:
    def test_load_by_path(self) -> None:
        data = {"template_name": "test", "template_version": "1.0", "layers": {}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            result = load_template(f.name)
        assert result["template_name"] == "test"

    def test_load_missing_file(self) -> None:
        try:
            load_template("/nonexistent/template.json")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass


# ============================================================================
# Runner
# ============================================================================


if __name__ == "__main__":
    import traceback

    # Collect all test classes and methods
    test_classes = [
        v
        for k, v in sorted(globals().items())
        if k.startswith("Test") and isinstance(v, type)
    ]
    passed = 0
    failed = 0
    for cls in test_classes:
        methods = [m for m in sorted(dir(cls)) if m.startswith("test_")]
        for method_name in methods:
            instance = cls()
            fn = getattr(instance, method_name)
            try:
                fn()
                passed += 1
                print(f"  PASS: {cls.__name__}.{method_name}")
            except Exception:
                failed += 1
                print(f"  FAIL: {cls.__name__}.{method_name}")
                traceback.print_exc()
    print(f"\nResults: {passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(1 if failed else 0)
