# PharmaCore — Frontend

React + TypeScript + Vite web app for PharmaCore (by Medlink). Phase 0 skeleton:
a branded shell proving the design tokens are wired through Tailwind.

## Quick start
```bash
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173
```

## Checks (same as CI)
```bash
npm run lint       # eslint
npm run typecheck  # tsc --noEmit
npm run build      # tsc -b && vite build
```

## Stack
Vite · React 18 · TypeScript (strict) · Tailwind CSS (design tokens) · ESLint + Prettier.
Components (shadcn/ui), routing, data (TanStack Query), tables, and charts arrive
with the feature phases — see ../docs/09-technology-stack.md and ../docs/design/.

## Design tokens
`src/index.css` defines the token CSS variables (light + dark); `tailwind.config.js`
exposes them as Tailwind colors (`brand`, `ink`, `surface`, `line`).
