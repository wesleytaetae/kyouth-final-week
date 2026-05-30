# LLM Deal Assistant Web App

## Summary

We are turning the current FastAPI + React starter into a simple LLM-powered deal assistant for Amazon sale items stored in SQLite at `data/app.db`.

The app has two user modes:

- `Buyer`: asks for good deals currently in the dataset
- `Seller`: asks for pricing guidance for a product they want to sell

The backend will use `pandas` to load and query the `amazon_products` table efficiently, then send only relevant evidence to Gemini to generate a grounded response. The frontend should present a chat-style interface plus a ranked product results panel.

V1 goals:

- one-page web app
- buyer/seller mode toggle
- chat input and AI response
- ranked product recommendations/comparables
- browser-only chat history
- no auth
- no backend session persistence

## Product Behavior

### Buyer Flow

Example prompt:

`Are there any good deals for USB C cables now?`

Expected behavior:

- backend identifies product/category intent
- backend retrieves matching products from the dataset using pandas
- backend ranks products by relevance, discount, rating, and rating count
- Gemini writes a short recommendation summary grounded in those results
- frontend shows:
  - AI answer
  - ranked matching products
  - key values like discounted price, original price, rating, discount, and link

### Seller Flow

Example prompt:

`How should I price my iPhone 15 USB cable?`

Expected behavior:

- backend identifies the target product type
- backend finds comparable products from the dataset
- backend computes a suggested MYR price range from comparable sale prices
- Gemini writes a pricing recommendation with rationale
- frontend shows:
  - AI answer
  - suggested price range
  - supporting comparable products

## Backend Plan

### API

Add a new endpoint:

- `POST /api/assistant/query`

Request body:

```json
{
  "mode": "buyer",
  "message": "Are there any good deals for USB C cables now?",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

Response body:

```json
{
  "answer": "These USB-C cables look like strong deals...",
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
      "img_link": "...",
      "product_link": "...",
      "match_score": 0.92
    }
  ],
  "metadata": {
    "mode": "buyer",
    "query_terms": ["usb", "c", "cable"],
    "matched_count": 42,
    "confidence": "high"
  }
}
```

### Retrieval and Data Layer

Backend should add a pandas-based service that:

- loads `amazon_products` from SQLite at startup
- stores it in a DataFrame for fast filtering and ranking
- normalizes:
  - `product_name`
  - `category`
  - `about_product`
- computes helper columns such as:
  - numeric discount score
  - normalized rating score
  - review-volume-aware ranking score

Retrieval should be deterministic first:

- parse keywords from user prompt
- identify likely category/product intent
- filter matching rows in pandas
- rank by relevance plus deal quality
- pass only top evidence rows into Gemini

### Gemini Usage

Gemini should be used only for answer synthesis, not raw retrieval.

Gemini prompt should instruct the model to:

- use retrieved evidence first
- provide light general advice if helpful
- admit uncertainty if the dataset match is weak
- avoid inventing product facts not present in retrieved rows

### Fallback Behavior

If Gemini fails or times out, backend should still return:

- deterministic summary text
- ranked products
- confidence and metadata

## Frontend Plan

Replace the starter items page with a single-page assistant UI.

### Main UI Sections

- hero/header introducing the app
- buyer/seller toggle
- chat conversation panel
- input box and submit button
- product results panel for the latest response

### Desired Interaction

When a user submits a prompt:

- frontend calls `POST /api/assistant/query`
- loading state appears
- assistant response is rendered
- associated product matches appear beside or below the response

### Product Display Requirements

For each returned product, show:

- product name
- discounted price
- original price
- discount percentage
- rating
- rating count
- image
- outbound product link

### Session and History

V1 should keep history only in the browser:

- React state
- optionally `localStorage` so refresh does not wipe chat

No backend persistence is needed.

## Frontend Notes for Handoff

The frontend should feel like a chat-plus-catalog experience, not just a plain chatbot.

Key UX expectations:

- mode toggle should clearly change intent:
  - buyer = find good deals
  - seller = get pricing guidance
- answer panel should feel assistant-like
- product panel should feel evidence-backed
- seller answers should visually emphasize:
  - suggested price range
  - comparable listings
- buyer answers should visually emphasize:
  - best deals
  - why they are good

Suggested component breakdown:

- `ModeToggle`
- `ChatPanel`
- `MessageList`
- `PromptComposer`
- `ResultsPanel`
- `ProductCard` or `ProductTable`
- `AnswerSummary`

## Dependencies and Config

Backend will need:

- `pandas`
- Gemini Python SDK
- env vars:
  - `GEMINI_API_KEY`
  - optional `GEMINI_MODEL`

Existing SQLite path behavior should remain compatible with Docker first-launch seeding.

## Testing

### Backend

- buyer query returns relevant matching products
- seller query returns comparable products and a price range
- weak/no-match query returns low-confidence response
- Gemini failure still returns fallback output
- DataFrame load succeeds from SQLite

### Frontend

- mode toggle changes request payload
- loading state works
- success state renders answer plus products
- error state renders clearly
- browser-only history works as expected

## Assumptions

- dataset is the primary evidence source
- all prices are MYR
- pandas keeps the full dataset in memory at app startup
- no auth is required for v1
- no backend chat persistence is required for v1
- frontend is a single-page experience
