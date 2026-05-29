from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db import get_connection, init_db


class ItemCreate(BaseModel):
    name: str


class Item(BaseModel):
    id: int
    name: str
    created_at: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
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

