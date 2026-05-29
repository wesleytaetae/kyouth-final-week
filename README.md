# FastAPI + React + SQLite Starter

This repo contains:

- `backend/`: FastAPI app served by Uvicorn and managed with `uv`
- `frontend/`: React + TypeScript app served with Vite
- `docker-compose.yml`: runs both services together

## Run with Docker

```bash
docker compose up --build
```

Then open:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs

## Backend notes

- SQLite data is stored in a Docker volume mounted at `/data`
- The API exposes:
  - `GET /api/health`
  - `GET /api/items`
  - `POST /api/items`

## Run without Docker

Backend:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```
