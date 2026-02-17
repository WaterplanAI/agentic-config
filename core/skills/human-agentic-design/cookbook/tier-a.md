# Tier A: Zero-Dependency Prototyping

Single-file HTML with Tailwind CSS v4 CDN + DaisyUI v5 CDN. Zero build step, zero npm.

## CDN URLs (Pinned Versions)

```html
<!-- Tailwind CSS v4 CDN -->
<script src="https://cdn.tailwindcss.com/4.0"></script>

<!-- DaisyUI v5 CDN -->
<link href="https://cdn.jsdelivr.net/npm/daisyui@5/themes.css" rel="stylesheet" />
<link href="https://cdn.jsdelivr.net/npm/daisyui@5/full.css" rel="stylesheet" />
```

## HTML Boilerplate

```html
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PAGE_TITLE</title>
  <script src="https://cdn.tailwindcss.com/4.0"></script>
  <link href="https://cdn.jsdelivr.net/npm/daisyui@5/themes.css" rel="stylesheet" />
  <link href="https://cdn.jsdelivr.net/npm/daisyui@5/full.css" rel="stylesheet" />
  <style>
    :focus-visible { outline: 2px solid #4f46e5; outline-offset: 2px; }
  </style>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "PAGE_TITLE",
    "description": "PAGE_DESCRIPTION"
  }
  </script>
</head>
<body class="min-h-screen bg-base-100">
  <header class="navbar bg-base-200">
    <nav aria-label="Main navigation">
      <a data-testid="nav-home" href="/" class="btn btn-ghost text-xl">SITE_NAME</a>
    </nav>
  </header>

  <main class="container mx-auto px-4 py-8">
    <h1 class="text-4xl font-bold mb-6">PAGE_HEADING</h1>
    <!-- Page content here -->
  </main>

  <footer class="footer footer-center p-4 bg-base-200 text-base-content">
    <p>Built with Human-Agentic Design</p>
  </footer>

  <script>
    // URL-driven state
    const params = new URLSearchParams(window.location.search);

    function updateState(key, value) {
      const url = new URL(window.location);
      url.searchParams.set(key, value);
      window.history.pushState({}, '', url);
    }
  </script>
</body>
</html>
```

## Multi-Page Linking

For multi-page prototypes, create multiple HTML files in the same directory:

```
/tmp/claude-prototypes/<session-id>/
  index.html        # Home / landing
  about.html        # About page
  contact.html      # Contact page
```

Link between them with relative paths:
```html
<nav aria-label="Main navigation">
  <a data-testid="nav-home" href="index.html" class="btn btn-ghost">Home</a>
  <a data-testid="nav-about" href="about.html" class="btn btn-ghost">About</a>
  <a data-testid="nav-contact" href="contact.html" class="btn btn-ghost">Contact</a>
</nav>
```

## Theme Switching

DaisyUI supports theme switching via `data-theme` attribute:

```html
<html data-theme="light">
<!-- Available themes: light, dark, cupcake, bumblebee, emerald, corporate, synthwave, retro, cyberpunk, valentine, halloween, garden, forest, aqua, lofi, pastel, fantasy, wireframe, black, luxury, dracula, cmyk, autumn, business, acid, lemonade, night, coffee, winter, dim, nord, sunset -->
```

```javascript
// Toggle theme
function toggleTheme() {
  const html = document.documentElement;
  html.setAttribute('data-theme',
    html.getAttribute('data-theme') === 'light' ? 'dark' : 'light'
  );
}
```

## Vanilla JS Patterns

- Use `document.querySelector('[data-testid="..."]')` for element selection
- Use `addEventListener` (never inline `onclick`)
- Use `URLSearchParams` for state management
- Use `fetch()` for any async data (mock with local JSON if needed)
- Use `<template>` elements for client-side rendering patterns
