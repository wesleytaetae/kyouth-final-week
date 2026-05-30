from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, StringConstraints

from app.assistant import load_products_dataframe, run_assistant_query
from app.db import amazon_products_count, get_connection, init_db
from app.import_amazon_xlsx import DEFAULT_WORKBOOK_PATH, import_workbook


class ItemCreate(BaseModel):
    name: str


class Item(BaseModel):
    id: int
    name: str
    created_at: str


class AssistantQuery(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AssistantMetadata(BaseModel):
    mode: Literal["buyer", "seller"]
    query_terms: list[str]
    matched_count: int
    confidence: Literal["high", "medium", "low"]
    llm_used: bool
    llm_error: str | None
    database_path: str


class ProductMatch(BaseModel):
    product_id: str
    product_name: str
    category: str | None
    discounted_price_myr: float | None
    actual_price_myr: float | None
    discount_percentage: float | None
    rating: float | None
    rating_count: int
    img_link: str | None
    product_link: str | None
    match_score: float | None


class AssistantResponse(BaseModel):
    answer: str
    products: list[ProductMatch]
    metadata: AssistantMetadata


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if DEFAULT_WORKBOOK_PATH.exists() and amazon_products_count() == 0:
        import_workbook(DEFAULT_WORKBOOK_PATH, replace=False)
    load_products_dataframe()
    yield


app = FastAPI(title="Simple App API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/items", response_model=list[Item])
def list_items() -> list[Item]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, created_at FROM items ORDER BY id DESC"
        ).fetchall()
    return [Item(**dict(row)) for row in rows]


@app.post("/api/items", response_model=Item, status_code=201)
def create_item(payload: ItemCreate) -> Item:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO items (name) VALUES (?)",
            (payload.name,),
        )
        connection.commit()
        row = connection.execute(
            "SELECT id, name, created_at FROM items WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return Item(**dict(row))


@app.post("/api/buyer/query", response_model=AssistantResponse)
def buyer_query(payload: AssistantQuery) -> AssistantResponse:
    return AssistantResponse(**run_assistant_query("buyer", payload.message))


@app.post("/api/seller/query", response_model=AssistantResponse)
def seller_query(payload: AssistantQuery) -> AssistantResponse:
    return AssistantResponse(**run_assistant_query("seller", payload.message))
