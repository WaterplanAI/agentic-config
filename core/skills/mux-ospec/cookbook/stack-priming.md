# Stack Priming for MUX-OSPEC

Stack-specific context injection for optimal agent performance.

## Multi-Stack Detection

### Detection Strategy

Analyze project structure to identify active technology stacks.

```bash
# Stack detection heuristics
detect_stacks() {
    local stacks=()

    # Frontend detection
    [[ -f package.json ]] && grep -q "react" package.json && stacks+=("react")
    [[ -f package.json ]] && grep -q "vue" package.json && stacks+=("vue")
    [[ -f package.json ]] && grep -q "@angular" package.json && stacks+=("angular")

    # Backend detection
    [[ -f pyproject.toml ]] && stacks+=("python")
    [[ -f go.mod ]] && stacks+=("go")
    [[ -f package.json ]] && grep -qE "express|fastify|koa" package.json && stacks+=("node")

    # Infrastructure detection
    [[ -d cdk ]] || [[ -f cdk.json ]] && stacks+=("cdk")
    [[ -f main.tf ]] || [[ -d terraform ]] && stacks+=("terraform")
    [[ -f pulumi.yaml ]] && stacks+=("pulumi")

    # Testing detection
    [[ -f jest.config.js ]] || [[ -f jest.config.ts ]] && stacks+=("jest")
    [[ -f pytest.ini ]] || [[ -f pyproject.toml ]] && stacks+=("pytest")
    [[ -f playwright.config.ts ]] && stacks+=("playwright")

    echo "${stacks[@]}"
}
```

### Manifest Generation

```yaml
# {session}/context/stack-manifest.yml
stacks:
  primary: react
  secondary:
    - node
    - jest
    - playwright
  infrastructure: cdk

detection:
  confidence: high
  indicators:
    react: ["package.json:react", "src/App.tsx"]
    node: ["package.json:express", "src/server/"]
    jest: ["jest.config.ts", "__tests__/"]
    cdk: ["cdk.json", "lib/*.ts"]
```

## Context Manifest Generation

### Structure

```yaml
# {session}/context/manifest.yml
version: 1
spec_path: specs/2026/02/feature-xyz/001-title.md
session_id: mux-20260204-103042

context:
  total_tokens: 45000
  budget: 80000
  allocation:
    spec: 15000
    stack_context: 12000
    dependencies: 8000
    patterns: 10000

stacks:
  - name: react
    context_file: context/react-prime.md
    tokens: 4000
  - name: node
    context_file: context/node-prime.md
    tokens: 3500
  - name: cdk
    context_file: context/cdk-prime.md
    tokens: 4500
```

### Generation Script

```python
# tools/generate-context-manifest.py
def generate_manifest(session_path, spec_path, stacks):
    manifest = {
        "version": 1,
        "spec_path": spec_path,
        "session_id": session_path.name,
        "context": {
            "total_tokens": 0,
            "budget": 80000,
            "allocation": {}
        },
        "stacks": []
    }

    for stack in stacks:
        context_file = f"context/{stack}-prime.md"
        tokens = estimate_tokens(session_path / context_file)
        manifest["stacks"].append({
            "name": stack,
            "context_file": context_file,
            "tokens": tokens
        })
        manifest["context"]["total_tokens"] += tokens

    return manifest
```

## Stack-Specific Priming Patterns

### Frontend: React

```markdown
# React Context Prime

## Project Structure
- Component architecture: {atomic|feature-based|domain-driven}
- State management: {redux|zustand|jotai|context}
- Styling: {tailwind|styled-components|css-modules}

## Conventions
- Component naming: PascalCase
- Hook prefix: use*
- Test files: *.test.tsx co-located

## Key Patterns
- Custom hooks for shared logic
- Compound components for complex UI
- Error boundaries at feature level
- Suspense for async operations

## Dependencies
{extracted from package.json}

## Anti-Patterns to Avoid
- Prop drilling beyond 2 levels
- Business logic in components
- Direct DOM manipulation
```

### Frontend: Vue

```markdown
# Vue Context Prime

## Project Structure
- Composition API vs Options API: {composition|options|mixed}
- State management: {pinia|vuex}
- Build tool: {vite|webpack}

## Conventions
- Component naming: PascalCase for SFC
- Composables: use* prefix
- Props: defineProps with TypeScript

## Key Patterns
- Composables for reusable logic
- Provide/inject for dependency injection
- Teleport for modals/portals

## Dependencies
{extracted from package.json}
```

### Frontend: Angular

```markdown
# Angular Context Prime

## Project Structure
- Module architecture: {standalone|ngmodule}
- State management: {ngrx|ngxs|signals}
- Version: {major version}

## Conventions
- Feature modules with lazy loading
- Smart/dumb component pattern
- Injectable services for business logic

## Key Patterns
- Signals for reactive state (Angular 16+)
- Change detection strategy: OnPush
- Standalone components (Angular 15+)

## Dependencies
{extracted from package.json}
```

### Backend: Node

```markdown
# Node.js Context Prime

## Project Structure
- Framework: {express|fastify|koa|nestjs}
- Runtime: {node|bun|deno}
- Module system: {esm|commonjs}

## Conventions
- Controller/Service/Repository layers
- Middleware for cross-cutting concerns
- Error handling middleware at app level

## Key Patterns
- Async/await for all I/O
- Dependency injection (manual or framework)
- Request validation at controller entry

## Dependencies
{extracted from package.json}

## Database Patterns
- ORM: {prisma|typeorm|drizzle|knex}
- Connection pooling configuration
```

### Backend: Python

```markdown
# Python Context Prime

## Project Structure
- Framework: {fastapi|django|flask}
- Package manager: {uv|poetry|pip}
- Python version: {version}

## Conventions
- Type hints for all public functions
- Pydantic for validation (FastAPI)
- SQLAlchemy or Django ORM

## Key Patterns
- Dependency injection via FastAPI Depends
- Async endpoints where beneficial
- Structured logging with structlog

## Dependencies
{extracted from pyproject.toml}

## Quality Tools
- Linter: ruff
- Type checker: pyright
- Formatter: ruff format
```

### Backend: Go

```markdown
# Go Context Prime

## Project Structure
- Layout: {standard|flat|domain-driven}
- Framework: {stdlib|gin|echo|fiber}
- Module path: {go.mod module}

## Conventions
- Interfaces accepted, structs returned
- Error handling: explicit returns
- Context propagation for cancellation

## Key Patterns
- Table-driven tests
- Functional options pattern
- Middleware chaining

## Dependencies
{extracted from go.mod}

## Project Layout
- cmd/: Application entrypoints
- internal/: Private packages
- pkg/: Public packages (if any)
```

### Infrastructure: CDK

```markdown
# AWS CDK Context Prime

## Project Structure
- Language: {typescript|python|go}
- CDK version: {version}
- Stack organization: {single|multi-stack}

## Conventions
- Construct naming: PascalCase
- Stack props interface per stack
- Environment-specific configuration

## Key Patterns
- L2/L3 constructs preferred over L1
- Aspects for cross-cutting concerns
- Custom constructs for reuse

## Stacks
{extracted from cdk.json and lib/}

## Synthesis
- cdk synth for CloudFormation output
- cdk diff before deploy
```

### Infrastructure: Terraform

```markdown
# Terraform Context Prime

## Project Structure
- Layout: {flat|modules|workspaces}
- Version: {terraform version}
- Backend: {s3|gcs|local}

## Conventions
- Resource naming: provider_type_name
- Variables in variables.tf
- Outputs in outputs.tf

## Key Patterns
- Modules for reusable infrastructure
- Data sources for external references
- Locals for computed values

## Modules
{extracted from module sources}

## State Management
- Remote state with locking
- State file per environment
```

### Testing: Jest

```markdown
# Jest Context Prime

## Configuration
- Test pattern: {pattern from config}
- Transform: {babel|ts-jest|swc}
- Coverage threshold: {if configured}

## Conventions
- describe/it block structure
- Arrange-Act-Assert pattern
- Mock files in __mocks__/

## Key Patterns
- jest.mock for module mocking
- Custom matchers for domain assertions
- Snapshot testing for UI (sparingly)

## Setup
- Setup files: {from config}
- Global mocks: {identified}
```

### Testing: Pytest

```markdown
# Pytest Context Prime

## Configuration
- Config location: {pytest.ini|pyproject.toml}
- Plugins: {installed plugins}
- Fixtures: {conftest.py locations}

## Conventions
- test_*.py file naming
- test_* function naming
- Fixtures for setup/teardown

## Key Patterns
- Parametrized tests for variants
- Markers for test categorization
- Factory fixtures for test data

## Fixtures
{extracted from conftest.py files}
```

### Testing: Playwright

```markdown
# Playwright Context Prime

## Configuration
- Browsers: {configured browsers}
- Base URL: {baseURL}
- Projects: {test projects}

## Conventions
- Page Object Model for complex flows
- Locator strategies: getByRole preferred
- Test isolation per test

## Key Patterns
- expect(locator) for assertions
- test.step for logical groupings
- Fixtures for authenticated state

## Helpers
{extracted from fixtures and helpers}
```

## Context Size Management

### Token Budget Allocation

```yaml
# Default allocation strategy
budget:
  total: 80000
  reserved:
    spec: 20%         # Spec content
    stack: 15%        # Stack priming
    dependencies: 10% # Key dependencies
    patterns: 12%     # Code patterns
    working: 43%      # Agent working memory
```

### Pruning Strategy

When context exceeds budget:

1. **Priority 1**: Preserve spec and success criteria
2. **Priority 2**: Keep primary stack context
3. **Priority 3**: Retain active file patterns
4. **Priority 4**: Summarize secondary stacks
5. **Priority 5**: Remove historical context

```python
def prune_context(manifest, target_tokens):
    """Prune context to fit within token budget."""
    current = manifest["context"]["total_tokens"]

    if current <= target_tokens:
        return manifest

    # Prune in priority order (lowest priority first)
    prune_order = [
        "historical",
        "secondary_stacks",
        "patterns",
        "dependencies"
    ]

    for category in prune_order:
        if current <= target_tokens:
            break
        current = prune_category(manifest, category, current, target_tokens)

    return manifest
```

### Dynamic Context Loading

```python
# Load context based on current phase
def load_phase_context(session, phase, spec_path):
    """Load appropriate context for execution phase."""

    base_context = load_spec_context(spec_path)

    if phase == "implement":
        # Full stack context for implementation
        return base_context + load_all_stack_context(session)

    elif phase == "review":
        # Spec + implementation focus
        return base_context + load_implementation_summary(session)

    elif phase == "test":
        # Testing stack context only
        return base_context + load_test_stack_context(session)

    return base_context
```

## Integration with MUX

### Priming Task Template

```python
Task(
    prompt=f"""Generate stack priming context.

PROJECT: {project_root}
SPEC: {spec_path}
SESSION: {session_path}

1. Run stack detection
2. Generate context manifest
3. Create stack-specific prime files

OUTPUT: {{session}}/context/manifest.yml
SIGNAL: {{session}}/.signals/priming.done

Return EXACTLY: done""",
    model="sonnet",
    run_in_background=True
)
```

### Context Injection

```python
# Inject context into agent prompts
def build_agent_prompt(base_prompt, session, stack_filter=None):
    manifest = load_manifest(session / "context/manifest.yml")

    context_parts = [base_prompt]

    for stack in manifest["stacks"]:
        if stack_filter and stack["name"] not in stack_filter:
            continue
        context_parts.append(
            read_file(session / stack["context_file"])
        )

    return "\n\n".join(context_parts)
```
