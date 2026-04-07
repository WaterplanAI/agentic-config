# Semantic HTML Validation Checklist

Run these checks on EVERY generated prototype before delivering to user.

## Mandatory Checks

| # | Check | How to Verify | Fail Action |
|---|-------|---------------|-------------|
| 1 | Exactly one `<main>` | Count `<main>` elements | Add or deduplicate |
| 2 | Exactly one `<h1>` | Count `<h1>` elements | Add or deduplicate |
| 3 | Heading hierarchy | No skipped levels (h1->h3 without h2) | Fix hierarchy |
| 4 | `data-testid` on interactive elements | Check all `<button>`, `<input>`, `<select>`, `<textarea>`, `<a>` | Add missing testids |
| 5 | No `<div onclick>` | Search for `onclick` on non-interactive elements | Replace with `<button>` |
| 6 | Label associations | Every `<input>` has `<label for>` or `aria-label` | Add label |
| 7 | JSON-LD present | `<script type="application/ld+json">` exists | Add JSON-LD block |
| 8 | No Shadow DOM | No `attachShadow` or `shadowrootmode` | Remove Shadow DOM |
| 9 | `<nav>` has `aria-label` | Each `<nav>` has descriptive `aria-label` | Add aria-label |
| 10 | Focus indicator | `:focus-visible` style defined | Add focus style |

## Using Playwright MCP Snapshot for Validation

After `mcp__playwright__browser_snapshot()`, the output is an accessibility tree. Verify:

```
Expected landmarks (minimum):
- main (exactly 1)
- navigation (at least 1)
- heading level 1 (exactly 1)
- banner (header)
- contentinfo (footer)

For form pages:
- textbox elements have accessible names
- button elements have accessible names
- combobox elements have accessible names

For dashboard pages:
- table elements present
- heading elements for sections

For blog pages:
- article elements present
- heading elements within articles
```

## Automated Snippet

When Playwright MCP is available, use `browser_snapshot()` output to check:

1. Search output for `main` landmark -- must appear exactly once
2. Search output for `heading "..."` at level 1 -- must appear exactly once
3. Search output for `navigation` -- must appear at least once
4. Search output for `button` -- each must have an accessible name (non-empty)
5. Search output for `textbox` -- each must have an accessible name (non-empty)

If any check fails: fix the HTML, rewrite the file, and re-snapshot.

## Manual Validation (No Playwright)

If Playwright MCP unavailable, visually inspect the generated HTML:
1. Open in browser
2. Use browser DevTools Accessibility panel
3. Check Elements panel for landmark structure
4. Verify tab order follows visual layout
