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

- SQLite data is stored by default in `data/app.db`
- In Docker, the backend seeds `amazon_products` from `data/amazon.xlsx` on first launch if the table is empty
- The API exposes:
  - `GET /api/health`
  - `GET /api/items`
  - `POST /api/items`

## Import `amazon.xlsx` into SQLite

The workbook already lives at `data/amazon.xlsx`. To load it into the backend database:

```bash
cd backend
uv run python -m app.import_amazon_xlsx --replace
```

This creates or refreshes the `amazon_products` table in SQLite using the Excel columns shown in your dataset.

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
