# Test Commands by Repository Type

Framework-specific test commands for adaptive execution. Reference: `tools/detect-repo-type.py`.

## Command Reference

| Framework | Detection | lint_cmd | unit_cmd | e2e_cmd |
|-----------|-----------|----------|----------|---------|
| CDK | `cdk.json` | `cdk synth` | `pytest infra/tests/` | N/A |
| Terraform | `terraform/` or `*.tf` | `terraform validate` | `terraform plan` | N/A |
| Vitest | `vitest` in deps | `tsc --noEmit` | `npm test` | `npx playwright test`* |
| Jest | `jest` in deps | `tsc --noEmit` | `npm test` | `npx playwright test`* |
| Playwright | `@playwright/test` only | `tsc --noEmit` | N/A | `npx playwright test` |
| Pytest | `pytest` in pyproject.toml | `ruff check && pyright` | `pytest -m unit` | `pytest -m e2e` |

*Only when `@playwright/test` present in deps.

## Detection Priority

1. CDK (infrastructure-first)
2. Terraform (infrastructure)
3. Vitest (preferred JS test runner)
4. Jest (legacy JS test runner)
5. Playwright (e2e-only projects)
6. Pytest (Python projects)
7. Unknown (fallback)

## Framework Details

### CDK

```yaml
detection: cdk.json exists
lint_cmd: cdk synth
unit_cmd: pytest infra/tests/
e2e_cmd: null
```

CDK synth validates infrastructure code by synthesizing CloudFormation templates.

### Terraform

```yaml
detection: terraform/ directory OR *.tf files
lint_cmd: terraform validate
unit_cmd: terraform plan
e2e_cmd: null
```

Validation checks HCL syntax; plan verifies resource configuration.

### Vitest

```yaml
detection: vitest in package.json dependencies
lint_cmd: tsc --noEmit
unit_cmd: npm test
e2e_cmd: npx playwright test (if @playwright/test present)
```

Modern Vite-native test runner with ESM support.

### Jest

```yaml
detection: jest in package.json dependencies
lint_cmd: tsc --noEmit
unit_cmd: npm test
e2e_cmd: npx playwright test (if @playwright/test present)
```

Established test runner for JavaScript/TypeScript projects.

### Playwright

```yaml
detection: @playwright/test only (no vitest/jest)
lint_cmd: tsc --noEmit
unit_cmd: null
e2e_cmd: npx playwright test
```

Browser automation focused projects without unit tests.

### Pytest

```yaml
detection: pytest in pyproject.toml
lint_cmd: ruff check && pyright
unit_cmd: pytest -m unit
e2e_cmd: pytest -m e2e
```

Python test framework with marker-based test categorization.

## Usage in MUX-OSPEC

```python
# Auto-detect and execute
result = detect_framework(project_path)

if result["unit_cmd"]:
    Bash(command=result["unit_cmd"])

if result["e2e_cmd"]:
    Bash(command=result["e2e_cmd"])
```

## Unknown Framework Fallback

When no framework detected, all commands return `null`. Manual configuration required via spec `TEST_COMMANDS` section.
