# Backend README

## Overview

This backend serves a FastAPI API backed by SQLite. It now includes two Gemini-powered assistant endpoints that work against the `amazon_products` dataset in `data/app.db`.

The assistant flow is:

1. load products from SQLite into a pandas DataFrame
2. normalize and keyword-match the user query
3. rank matching products for buyer or seller intent
4. send the top matches to Gemini for the final answer
5. fall back to a deterministic summary if Gemini is unavailable

## Endpoints

### `POST /api/buyer/query`

Use this for shopper questions like:

- `Are there any good deals for USB C cables now?`

Request body:

```json
{
  "message": "Are there any good deals for USB C cables now?"
}
```

### `POST /api/seller/query`

Use this for seller pricing questions like:

- `How should I price my iPhone 15 USB cable?`

Request body:

```json
{
  "message": "How should I price my iPhone 15 USB cable?"
}
```

### Response shape

Both endpoints return:

```json
{
  "answer": "Assistant response text",
  "products": [
    {
      "product_id": "B098NS6PVG",
      "product_name": "Ambrane Unbreakable 60W...",
      "category": "Computers&Accessories|...",
      "discounted_price_myr": 8.32,
      "actual_price_myr": 14.59,
      "discount_percentage": 0.43,
      "rating": 4.0,
      "rating_count": 43994,
      "img_link": "https://...",
      "product_link": "https://...",
      "match_score": 0.92
    }
  ],
  "metadata": {
    "mode": "buyer",
    "query_terms": ["usb", "cable"],
    "matched_count": 42,
    "confidence": "high",
    "llm_used": true,
    "llm_error": null,
    "database_path": "/absolute/path/to/app.db"
  }
}
```

## Environment

Create `backend/.env` based on `backend/.env.example`.

Required:

- `GEMINI_API_KEY`

Supported:

- `DATABASE_PATH`
- `GEMINI_MODEL`

Default model:

- `gemini-2.5-flash-lite`

Note:

- you asked for `gemini-3.1-flash-lite`, but Google’s public Gemini model docs currently list `gemini-2.5-flash-lite` as the active Flash-Lite model. If you have access to a different model string, set it in `GEMINI_MODEL`.

## Local Run

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

## Docker Run

Docker Compose now reads environment values from `backend/.env`.
In Docker, `DATABASE_PATH` is explicitly overridden to `/app/data/app.db` so the backend uses the mounted SQLite volume instead of an unintended relative path.

```bash
docker compose up --build
```

## Notes on Retrieval

The backend does not let Gemini query SQLite directly.

Instead:

- pandas loads the `amazon_products` table into memory
- the query is normalized into searchable keywords
- category tokens are normalized too, so values like `SmartTelevisions` can match prompts like `smart tv`
- category-aware synonyms now cover common dataset families like `smartwatch`, `earbuds`, `router`, `power bank`, `geyser`, `pendrive`, `water purifier`, and `keyboard mouse combo`
- ranking instructions like `highest rated`, `cheapest`, and `best deal` are treated as sort intent instead of product keywords
- queries like `most expensive` are also treated as sort intent
- response-size instructions like `only 1 answer` or `top 3` control how many products are returned in the JSON
- phrases like `single most expensive` also force a one-product JSON response
- product matches are ranked deterministically
- Gemini only writes the final answer from those retrieved rows

This keeps answers more grounded and predictable.
