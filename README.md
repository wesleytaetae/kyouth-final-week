# LLM Deal Assistant

This project is a small full-stack shopping assistant built with FastAPI, React, and SQLite. It loads Amazon marketplace product data from `data/amazon.xlsx`, stores it in SQLite, and lets users ask for product recommendations in either:

- `buyer` mode: find strong deals, cheapest items, highest-rated products, or category matches
- `seller` mode: find comparable listings and suggest a competitive pricing range

The backend does deterministic search and ranking over the local dataset, and can optionally use Gemini to:

- rewrite the final answer in a more natural way
- re-rank or filter the top candidate products for better semantic relevance

If Gemini is not configured, the app still works using the local scoring pipeline only.

## Project structure

- `backend/`: FastAPI API, SQLite access, Excel import, search/ranking, optional Gemini integration
- `Data Component`: module for importing marketplace data from `.xlsx` files into SQLite, mainly in `backend/app/import_amazon_xlsx.py`
- `AI Component`: module for AI-assisted product filtering and answer generation, mainly in `backend/app/assistant.py`
- `frontend/`: React + TypeScript UI built with Vite
- `data/amazon.xlsx`: source dataset
- `data/app.db`: SQLite database used by the backend
- `docker-compose.yml`: runs frontend and backend together

## How to run

### Option 1: Docker Compose

Make sure `backend/.env` exists and contains at least:

```env
DATABASE_PATH=../data/app.db
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
```

Then run:

```bash
docker compose up --build
```

Open:

- Frontend: `http://localhost:5173`
- Backend API docs: `http://localhost:8000/docs`
- Backend health check: `http://localhost:8000/api/health`

Notes:

- The backend container stores SQLite at `/app/data/app.db`
- On startup, the backend initializes tables and imports `amazon.xlsx` if `amazon_products` is empty

### Option 2: Run locally without Docker

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

The frontend defaults to calling `http://localhost:8000`. To point it elsewhere:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## How to use the app

1. Open the frontend in the browser.
2. Pick `Buyer Mode` or `Seller Mode` from the header.
3. Type a question or click one of the starter prompts.
4. Read the answer in the left chat panel.
5. Inspect matching product cards in the right results panel.

Example buyer prompts:

- `Any good options for a smart tv?`
- `What is the highest rated product available? Give me only 1 answer.`
- `Are there any good deals for USB-C cables now?`

Example seller prompts:

- `How should I price my iPhone 15 USB cable?`
- `What is the single most expensive item on sale in the market now?`
- `How should I price a smart watch competitively?`

The backend understands a few useful query patterns automatically, including:

- quantity hints like `top 3` or `only 1`
- sort intent like `highest rated`, `cheapest`, `best deal`, `most expensive`
- synonym normalization like `usb-c` -> `usb c`, `power bank` -> `powerbank`, `tv` -> `television`

## Data flow

### Startup flow

1. FastAPI starts and runs the lifespan hook.
2. The backend creates the `items` and `amazon_products` tables if needed.
3. If `data/amazon.xlsx` exists and `amazon_products` is empty, the workbook is imported into SQLite.
4. The backend loads the `amazon_products` table into a cached pandas DataFrame.
5. It derives normalized search text and a `deal_score` used for ranking.

### Query flow

1. The frontend sends `POST /api/buyer/query` or `POST /api/seller/query` with `{ "message": "..." }`.
2. The backend parses the message into:
   - keywords
   - sort mode
   - requested result limit
3. It scores products against the cached dataset:
   - buyer mode blends keyword relevance and deal quality
   - seller mode favors comparable product relevance, rating, and lower-discount comparables
4. It builds a candidate pool from the ranked matches.
5. If Gemini is configured and there are enough candidates, the backend may ask Gemini to filter the candidate list.
6. The backend generates:
   - `products`: structured product matches for the UI
   - `answer`: Gemini-written answer or deterministic fallback summary
   - `metadata`: mode, query terms, match confidence, LLM usage, and database path
7. The frontend appends the answer to the chat log and renders the returned products as cards.

## Backend endpoints

### `GET /api/health`

Simple health check.

Response:

```json
{ "status": "ok" }
```

### `GET /api/items`

Returns the demo `items` table rows ordered newest first.

### `POST /api/items`

Creates a row in the demo `items` table.

Request:

```json
{ "name": "example item" }
```

### `POST /api/buyer/query`

Runs the buyer assistant over the local Amazon dataset.

Request:

```json
{ "message": "Any good options for a smart tv?" }
```

### `POST /api/seller/query`

Runs the seller assistant over the same dataset and returns comparable products plus pricing guidance.

Request:

```json
{ "message": "How should I price a smart watch competitively?" }
```

### Buyer and seller response shape

Both query endpoints return:

```json
{
  "answer": "Natural-language recommendation",
  "products": [
    {
      "product_id": "B0...",
      "product_name": "Product name",
      "category": "Category",
      "discounted_price_myr": 199.9,
      "actual_price_myr": 249.9,
      "discount_percentage": 20.0,
      "rating": 4.4,
      "rating_count": 1234,
      "img_link": "https://...",
      "product_link": "https://...",
      "match_score": 0.87
    }
  ],
  "metadata": {
    "mode": "buyer",
    "query_terms": ["smart", "television"],
    "matched_count": 18,
    "confidence": "high",
    "llm_used": true,
    "llm_error": null,
    "llm_filter_used": true,
    "llm_filter_error": null,
    "database_path": "/absolute/path/to/app.db"
  }
}
```

## Database and import flow

The SQLite schema includes:

- `items`: small demo table used by the starter endpoints
- `amazon_products`: imported Amazon catalog and review fields

The import script is:

```bash
cd backend
uv run python -m app.import_amazon_xlsx --replace
```

What it does:

- reads `data/amazon.xlsx` directly from the workbook XML
- maps spreadsheet headers into database columns
- parses numeric values like prices, ratings, counts, and discounts
- upserts rows using `source_row_number` as the unique source identity

Useful flags:

- `--replace`: clears existing `amazon_products` rows before import
- `--xlsx <path>`: import a different workbook
- `--db <path>`: write to a different SQLite file

## Frontend design

The frontend is intentionally split into a conversational workspace and a visual evidence panel.

### Layout

- top header with the product title and buyer/seller mode switch
- left 40% panel for chat history and prompt input
- right 60% panel for product evidence cards

### Visual style

- warm cream-to-sand background with radial highlights
- dark navy header and user message bubbles
- rounded panels with light blur and soft borders
- amber call-to-action buttons and rating accents
- product cards with discount badges, pricing hierarchy, and external product links

### Interaction model

- starter prompts change based on the selected mode
- every new query clears the current result cards before loading fresh ones
- the left panel keeps a conversational log
- the right panel shows structured product cards from the backend response
- assistant messages support simple `**bold**` formatting

## Environment and configuration

Backend environment variables:

- `DATABASE_PATH`: SQLite database path
- `GEMINI_API_KEY`: enables Gemini answer generation and candidate filtering
- `GEMINI_MODEL`: optional override, defaults to `gemini-2.5-flash-lite`

Frontend environment variables:

- `VITE_API_BASE_URL`: backend base URL, defaults to `http://localhost:8000`

## Tech stack

- Backend: FastAPI, pandas, SQLite, python-dotenv, Google GenAI SDK
- Frontend: React 18, TypeScript, Vite
- Tooling: `uv`, Docker, Docker Compose
