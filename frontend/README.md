# DarGlobal × Wasalt — Frontend

Production frontend for the real-estate intelligence assistant. React 18 + Vite + plain
CSS, with `lucide-react` for icons. No API keys live here.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

Vite serves on <http://localhost:5173>. The app talks to the backend at
`http://localhost:8000` by default.

## Configure the backend URL

Create an optional `.env` file in this directory:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

Only `VITE_API_BASE_URL` is read. Never put secrets in frontend environment files —
anything prefixed with `VITE_` is bundled into public JavaScript.

## Build

```bash
npm run build
npm run preview   # serve the production build locally
```

The production output is written to `frontend/dist/`.
