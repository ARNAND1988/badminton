Frontend standalone repository

This folder contains the Vite + Vue frontend and can be used as its own repository.

If you split this folder into its own repository, ensure it includes:
- `package.json`, `vite.config.js`, `src/`, `index.html`, `postcss.config.cjs`, `tailwind.config.cjs`

See the top-level README for information about proxying API requests to the backend.
Vite + Vue3 frontend with Tailwind CSS

Quick start

1. Install dependencies

```bash
cd frontend
npm install
```

2. Run dev server (proxies `/api` to http://localhost:8000)

```bash
npm run dev
```

3. Build for production

```bash
npm run build
```
