# PLAN
STAGE: PLAN
GOAL: WRITE EXACT step by step implementation PLAN to achieve `SPEC` Objectives aligned with Details and Research. PLAN is a COMPLETE dry-run of the IMPLEMENT step. YOU CANNOT MISS ANY SINGLE DETAIL.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.
- YOU WILL ONLY EDIT THE SPEC.
- TASK should have the EXACT file, CONCISE description, tools, EXACT COMPLETE diff, verification instructions to use to SUCCESSFULLY accomplish TASK without further required reasoning.
- COMPLY EXACTLY with Behavior, Workflow AND Format.
- PLAN tasks will be implemented by a different entity.
  - You need to be ABSOLUTE clear to provide the EXACT step by step task IN ORDER.

## Behavior

- YOU ARE BOTH A SENIOR AI ENGINEER & A SENIOR PRODUCT MANAGER, ABOUT TO DELEGATE THE IMPLEMENTATION OF SPEC & PLAN to a VERY JUNIOR developer. INSTRUCTIONS need to be straight-forward to follow and require NO THINKING.

- COMPLY WITH your user instructions (RE-READ them and reflect them to user)

- If something is missing in the Plan for the Implementation to ACCURATELY AND COMPLETELY achieving `Human Section` objectives and details, you will be held responsible, not the entity that will act as implementor, not the human that wrote `Human Section`.

- PLAN unit tests for each implementation task to verify component-level correctness.

- PLAN e2e tests for feature-level validation to ensure end-to-end functionality.

## Workflow

1. REFLECT your understanding and what you will do (CONCISELY).
2. CONVERT the RESEARCH & STRATEGY into a CONCRETE IMPLEMENTATION PLAN.
3. PRESENT outline of tasks (number & title) to user.
4. LIST all the files (sub-bullets: lines) to be USED in a section `## Plan > ### Files`
5. EDIT SPEC: WRITE ONE TASK at a time in section `## Plan > ### Tasks > #### Task X` - AVOID BIG CHUNK EDITS - prefer small ones.
		1. TASK should have the EXACT file, CONCISE description, tools, EXACT COMPLETE diff, verification instructions to use to SUCCESSFULLY accomplish TASK without further required reasoning.
			1. DIFF blocks should be written in markdown "````diff" blocks with NO line indentation on the opening "````diff" and closing "````". NOTE THE FOUR ` (NOT THREE).
		2. TASK will be executed by a different entity WITH NO CONTEXT OTHER than SPEC.
		3. DIFF BLOCKS NEED TO BE EXACT. DO NOT LEAVE THEM INCOMPLETE OR ILLUSTRATIVE.
6. APPEND TASK to LINT (e.g.: ruff & pyright) EVERY file you have modified across all the steps.
7. APPEND TASK to write/update unit tests for each component modified.
8. APPEND TASK to perform E2E testing.
9. APPEND TASK to COMMIT ONLY specific files updated with clear commit message.
9. For TASKs that require it, CORRECTLY source .venv and .env in the same execution command (e.g.: source .venv/bin/activate && set -o allexport; source .env; set +o allexport && <python_cmd>)
10. RE-READ `Human Section` and VALIDATE you comply with every requirement.
   1. LIST EVERY requirement in a subsection `## Plan > ### Validate` and append a 1 line summary (with spec line reference `L<X>`) on how you are complying with that requirement.
11. SUMMARIZE result to user in output (max: 150 words).
12. COMMIT using spec resolver:
    ```bash
    # Source spec resolver (pure bash - no external commands)
    _agp=""
    [[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
    AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
    unset _agp
    source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"

    # Commit spec changes
    commit_spec_changes "<spec_path>" "PLAN" "<NNN>" "<title>"
    ```

## Format

1. LIST all the files (sub-bullets: lines) to be USED in a section `## Plan > ### Files`
2. WRITE each TASK (ONCE at a time) in section `## Plan > ### Tasks > #### Task X`
3. DIFF blocks should be written in markdown "```diff" blocks with NO line indentation on the opening "```diff" and closing "```"
4. Test tasks should follow implementation tasks: implementation → unit tests → e2e tests → lint → commit

### GOOD Example

`````md
## Plan

### Files
- lambdas/rf3_get_content/src/v5/content/models.py
  - Add `SynthesizedFact`; extend `FeaturesChecklist`; extend `SynthesisResult`.
- lambdas/rf3_get_content/src/v5/content/steps/extract_features.py
  - Update `SYSTEM_RULES` to require compact long_summary + `* <s_id>` bullets + `synthesized_facts`.
  - Relax header id validation to unique subset within range.
  - Enforce checklist `s_id_bullets_only`.
  - Post-process `* <s_id>` → text using `synthesized_facts`; enforce combined cap.

### Tasks

#### Task 1 — models.py: add SynthesizedFact and fields
Tools: editor
Diff:
````diff
--- a/lambdas/rf3_get_content/src/v5/content/models.py
+++ b/lambdas/rf3_get_content/src/v5/content/models.py
@@
 class WaterFact(BaseModel):
@@
     )

+class SynthesizedFact(BaseModel):
+    """Compact fact referenced by s_id bullets in long_summary."""
+    id: int = Field(..., ge=0, description="s_id used in long_summary bullets ('* <id>')")
+    text: str = Field(..., description="Exact compact fact text following prompt rules")
+
@@
 class FeaturesChecklist(BaseModel):
@@
     english_ascii_enforced: CheckboxScratchItem = Field(
         description="All headers are English ASCII; no diacritics"
     )
+    s_id_bullets_only: CheckboxScratchItem = Field(
+        description="Within 'Facts by Location', each bullet is exactly '* <s_id>'; no extra prose; all referenced s_id map to synthesized_facts"
+    )
@@
 class SynthesisResult(BaseModel):
@@
     long_summary: str = Field(
         description="Comprehensive summary with page references"
     )
+    synthesized_facts: list[SynthesizedFact] = Field(
+        default_factory=list,
+        description="List of SynthesizedFact whose ids are referenced by bullets in long_summary"
+    )
````

Verification:
- ruff/pyright on file.

#### Task 2 — extract_features.py: update SYSTEM_RULES and caps
Tools: editor
Diff (additions within SYSTEM_RULES, keep existing content):
````diff
--- a/lambdas/rf3_get_content/src/v5/content/steps/extract_features.py
+++ b/lambdas/rf3_get_content/src/v5/content/steps/extract_features.py
@@
 SYSTEM_RULES = """You are a water risk synthesis assistant producing strict, location-indexed summaries.
@@
 ### 3. long_summary (REQUIRED)
-**CRITICAL TOKEN LIMIT:** Maximum 10000 output tokens (approximately 40000 characters)
+**CRITICAL TOKEN LIMIT:** Maximum 10000 output tokens (approximately 40000 characters)
@@
-- OPTIONAL PRELUDE: Add short "## All Facts Summary" section BEFORE "## Facts by Location" with 3–7 bullets summarizing cross-location insights (≤600 chars total; must be supported by location facts with page ranges; no new claims; do not duplicate full details)
+- REQUIRED PRELUDE: Add "## All Facts Summary" BEFORE "## Facts by Location". Keep under 300 words, as bullets summarizing cross-location insights, supported by location facts with page ranges; no new claims; do not duplicate full details
@@
 - TOP-LEVEL "## Facts by Location" section with EXACTLY N subsections where N = len(header_index_map)
 - Each subsection header MUST be "###<id>" (no spaces). NEVER add, remove, rename, or reorder headers
-- Do NOT emit names in headers; use ids only. Section ordering: id ascending (0..N-1) strictly
- - GROUP BY LOCATION: Under each location subsection, list facts as bullets. Duplicate facts if they apply to multiple locations. Always include compact page ranges
+- Do NOT emit names in headers; use ids only. Section ordering: id ascending (0..N-1) strictly
+- GROUP BY LOCATION: Under each location subsection, emit bullets ONLY as "* <s_id>" (angle-bracketed integer). NO other prose, sub-headers, or splitters. Duplicate bullets across applicable locations
@@
 ### 4. scratchpad (REQUIRED)
@@
 ### 5. cse_citation (REQUIRED)
@@
 **Format:** Organization. Year. Title [Internet]. [updated YYYY Mon DD; cited {current_date}]
@@
-Respond ONLY with JSON matching SynthesisResult.
+### 6. synthesized_facts (REQUIRED)
+Return an array `synthesized_facts` of objects `{id:int, text:str}`. Each `id` MUST match a `* <id>` bullet in long_summary; each `text` follows compactation rules (quantitative first; include page ranges; no extra commentary).
+
+## CRITICAL MAX OUTPUT RULES
+- long_summary ≤ 10000 tokens (~40000 chars)
+- scratchpad ≤ 2000 tokens (~8000 chars)
+- Combined length cap: `len(long_summary) + sum(len(text) for synthesized_facts)` ≤ ~40000 chars. Keep long_summary short and shift details to synthesized_facts.
+
+Respond ONLY with JSON matching SynthesisResult.
"""
@@
+# Hard cap used for combined length check (approximate; aligns with SYSTEM_RULES)
+LONG_SUMMARY_MAX_CHARS = 40000
````

Verification:
- Visual inspect `SYSTEM_RULES` block for new requirements.

#### Task 3 — extract_features.py: subset header id validation
Tools: editor
Diff:
````diff
--- a/lambdas/rf3_get_content/src/v5/content/steps/extract_features.py
+++ b/lambdas/rf3_get_content/src/v5/content/steps/extract_features.py
@@
-        # Require ids cover 0..N-1 exactly once
-        if sorted(matched_ids) != list(range(len(header_index_map))):
-            expected_range = list(range(len(header_index_map)))
-            logger.error(f"Header IDs range mismatch. Found IDs (sorted): {sorted(matched_ids)}")
-            logger.error(f"Expected range: {expected_range}")
-            logger.error(f"Long summary (first 1500 chars):\n{long_summary[:1500]}")
-            # Create partial ParsingResult for debugging
-            context['parsing_result'] = ParsingResult(
-                title=synthesis_result.title if synthesis_result else "Validation Failed",
-                summary="",
-                long_summary=long_summary,
-                content_date=synthesis_result.best_publication_date.chosen_date if synthesis_result else None,  # type: ignore
-                source_type=EvidenceSourceType.OTHER,
-                locations=[],
-                sure_about_content_date_day=False,
-                sure_about_content_date_month=False,
-                cse_citation_fields=None,
-                significant_locations=significant_locations  # Pass through for location filter
-            )
-            raise ExplicitStepFailed(SearchResultStatus.EXTRACT_FEATURES_ERROR, 'Header ids must cover 0..N-1 exactly once')
+        # Require ids be a UNIQUE SUBSET of 0..N-1 (allow missing)
+        expected_range = set(range(len(header_index_map)))
+        matched_set = set(matched_ids)
+        out_of_range = [i for i in matched_ids if i < 0 or i >= len(header_index_map)]
+        if out_of_range or len(matched_ids) != len(matched_set) or not matched_set.issubset(expected_range):
+            logger.error(f"Header IDs subset invalid. Found IDs: {sorted(matched_ids)}; Expected subset of: {sorted(expected_range)}; Out-of-range: {out_of_range}; Duplicates?: {len(matched_ids) != len(matched_set)}")
+            logger.error(f"Long summary (first 1500 chars):\n{long_summary[:1500]}")
+            context['parsing_result'] = ParsingResult(
+                title=synthesis_result.title if synthesis_result else "Validation Failed",
+                summary="",
+                long_summary=long_summary,
+                content_date=synthesis_result.best_publication_date.chosen_date if synthesis_result else None,  # type: ignore
+                source_type=EvidenceSourceType.OTHER,
+                locations=[],
+                sure_about_content_date_day=False,
+                sure_about_content_date_month=False,
+                cse_citation_fields=None,
+                significant_locations=significant_locations
+            )
+            raise ExplicitStepFailed(SearchResultStatus.EXTRACT_FEATURES_ERROR, 'Header ids must be a unique subset of 0..N-1')
````

Verification:
- Re-run failure scenario; expect no failure when only a subset exists (no duplicates/out-of-range).

#### Task 4 — extract_features.py: enforce s_id bullets via checklist
Tools: editor
Diff:
````diff
--- a/lambdas/rf3_get_content/src/v5/content/steps/extract_features.py
+++ b/lambdas/rf3_get_content/src/v5/content/steps/extract_features.py
@@
-        if not fc or not (
+        if not fc or not (
             getattr(fc, 'only_indexed_headers_used', None) and getattr(fc.only_indexed_headers_used, 'is_checked', False) and
             getattr(fc, 'header_exact_match', None) and getattr(fc.header_exact_match, 'is_checked', False) and
-            getattr(fc, 'no_poc_headers', None) and getattr(fc.no_poc_headers, 'is_checked', False)
+            getattr(fc, 'no_poc_headers', None) and getattr(fc.no_poc_headers, 'is_checked', False) and
+            getattr(fc, 's_id_bullets_only', None) and getattr(fc.s_id_bullets_only, 'is_checked', False)
         ):
````

Verification:
- Confirm failure path triggers when s_id bullets rule not acknowledged.

#### Task 5 — extract_features.py: replace s_id bullets and enforce combined cap
Tools: editor
Diff:
````diff
--- a/lambdas/rf3_get_content/src/v5/content/steps/extract_features.py
+++ b/lambdas/rf3_get_content/src/v5/content/steps/extract_features.py
@@
         long_summary = pattern.sub(_repl, long_summary)
+        # Replace per-location bullets '* <s_id>' with synthesized_facts text within '## Facts by Location'
+        facts_header = re.search(r'^##\s*Facts by Location\s*$', long_summary, flags=re.MULTILINE)
+        syn_list = list(getattr(synthesis_result, 'synthesized_facts', []) or [])
+        if facts_header and syn_list:
+            syn_text_total = 0
+            try:
+                syn_text_total = sum(len(getattr(sf, 'text', '') or '') for sf in syn_list)
+            except Exception:
+                syn_text_total = 0
+            if len(long_summary) + syn_text_total > LONG_SUMMARY_MAX_CHARS:
+                logger.error(f"Combined cap exceeded: long_summary={len(long_summary)}, synthesized_facts_total={syn_text_total}, cap={LONG_SUMMARY_MAX_CHARS}")
+                raise ExplicitStepFailed(SearchResultStatus.EXTRACT_FEATURES_ERROR, 'Combined long_summary + synthesized_facts exceed max cap')
+
+            id_to_text: dict[int, str] = {}
+            for sf in syn_list:
+                try:
+                    sid = int(getattr(sf, 'id'))
+                    txt = str(getattr(sf, 'text') or '')
+                    if sid in id_to_text:
+                        raise ExplicitStepFailed(SearchResultStatus.EXTRACT_FEATURES_ERROR, f'duplicate synthesized_fact id {sid}')
+                    id_to_text[sid] = txt
+                except Exception as _:
+                    continue
+
+            start = facts_header.end()
+            prefix, suffix = long_summary[:start], long_summary[start:]
+            bullet_id_pattern = re.compile(r'^(\s*)\*\s*<(\d+)>\s*$', re.MULTILINE)
+
+            def _repl_bullet(m: re.Match[str]) -> str:
+                sid = int(m.group(2))
+                if sid not in id_to_text:
+                    raise ExplicitStepFailed(SearchResultStatus.EXTRACT_FEATURES_ERROR, f'Unknown synthesized_fact id <{sid}> in long_summary')
+                return f"{m.group(1)}* {id_to_text[sid]}"
+
+            replaced_suffix = bullet_id_pattern.sub(_repl_bullet, suffix)
+            # Ensure no residual id bullets remain
+            if re.search(r'^(\s*)\*\s*<\d+>\s*$', replaced_suffix, flags=re.MULTILINE):
+                logger.error("Residual '* <s_id>' bullets remain after replacement")
+                raise ExplicitStepFailed(SearchResultStatus.EXTRACT_FEATURES_ERROR, 'Unmapped s_id bullets remain after replacement')
+            long_summary = prefix + replaced_suffix
````

Verification:
- Confirm bullets are replaced and errors raise on unknown/missing ids.

#### Task 6 — Lint & Type-check (changed files only)
Tools: shell
Commands:
- `ruff check --fix lambdas/rf3_get_content/src/v5/content/models.py lambdas/rf3_get_content/src/v5/content/steps/extract_features.py`
- `PYTHONPATH=../risk-framework-v3-stack/lambdas/common_layer:$PYTHONPATH pyright lambdas/rf3_get_content/src/v5/content/models.py lambdas/rf3_get_content/src/v5/content/steps/extract_features.py || true`

#### Task 7 — E2E
Tools: shell
Commands:
- `set -euo pipefail; source ../../../../.venv/bin/activate; set -o allexport; source .env; set +o allexport; pushd ../../rf3_get_content/src >/dev/null; PYTHONPATH=../../risk-framework-v3-stack/lambdas/common_layer:$PYTHONPATH python -m src.v5.filtering.tests.test_e2e --sequential --log_level INFO; popd >/dev/null`

Expectations:
- Extract Features step no longer fails with subset headers.
- Long summary structure enforced; bullets replaced deterministically.

#### Task 8 — Commit
Tools: git
Commands:
- `git add -- lambdas/rf3_get_content/src/v5/content/models.py lambdas/rf3_get_content/src/v5/content/steps/extract_features.py`
- `BRANCH=$(git rev-parse --abbrev-ref HEAD); [ "$BRANCH" != "master" ] || { echo 'ERROR: On master' >&2; exit 2; }`
- `git commit -m "spec(118): IMPLEMENT - deterministic long_summary via s_id subset + post-processing"`

`````
