# Tier B: React + shadcn/ui + Vite

Production-grade prototype scaffold with HMR. Activated when Node.js detected.

## Prerequisites

- Node.js >= 18
- npm >= 9

## Scaffold Setup Commands

```bash
SESSION_DIR="/tmp/claude-prototypes/<session-id>"
mkdir -p "$SESSION_DIR"
cd "$SESSION_DIR"

# Create Vite project
npm create vite@latest . -- --template react-ts

# Install dependencies
npm install

# Add Tailwind CSS v4
npm install -D tailwindcss @tailwindcss/vite

# Add shadcn/ui
npx shadcn@latest init -d
```

## package.json (Key Dependencies)

```json
{
  "name": "prototype",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.0.0"
  }
}
```

## vite.config.ts

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

## File Structure

```
<session-id>/
  package.json
  vite.config.ts
  tsconfig.json
  index.html              # Vite entry HTML
  src/
    main.tsx              # React entry point
    App.tsx               # Root component with Router
    index.css             # Tailwind imports
    components/
      ui/                 # shadcn/ui components (code-distributed)
        button.tsx
        card.tsx
        input.tsx
        ...
      layout/
        Header.tsx
        Footer.tsx
        Sidebar.tsx
    pages/
      Home.tsx
      About.tsx
      ...
    lib/
      utils.ts            # cn() helper from shadcn
  public/
```

## App.tsx Template

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Header } from './components/layout/Header'
import { Footer } from './components/layout/Footer'
import { Home } from './pages/Home'

export function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Home />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </BrowserRouter>
  )
}
```

## Agent Principles in React

```tsx
// data-testid on all interactive elements
<button data-testid="signup-submit" className="btn btn-primary">Sign Up</button>

// Semantic HTML in JSX
<nav aria-label="Main navigation">...</nav>
<section aria-label="Features">...</section>
<article>...</article>

// Label associations
<label htmlFor="email-input">Email</label>
<input id="email-input" data-testid="email-input" type="email" />

// URL-driven state via React Router
import { useSearchParams } from 'react-router-dom'
const [searchParams, setSearchParams] = useSearchParams()
const view = searchParams.get('view') || 'grid'
```

## JSON-LD in React

Place in `index.html` `<head>` section (not in React component):

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Prototype Title"
}
</script>
```

## Start Dev Server

```bash
cd /tmp/claude-prototypes/<session-id>
npm run dev
# Opens on http://localhost:5173 (auto-increments if port taken)
```
