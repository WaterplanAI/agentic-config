# Running Code

Execute JavaScript directly in the browser page context.

## Basic Usage

```bash
# Get page title
playwright-cli run-code "document.title"

# Get element text
playwright-cli run-code "document.querySelector('h1').textContent"

# Get computed style
playwright-cli run-code "getComputedStyle(document.body).backgroundColor"
```

## Complex Scripts

```bash
# Count elements
playwright-cli run-code "document.querySelectorAll('.item').length"

# Extract data
playwright-cli run-code "JSON.stringify(Array.from(document.querySelectorAll('a')).map(a => a.href))"
```
