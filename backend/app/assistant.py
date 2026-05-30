import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google import genai

from app.db import DB_PATH, get_connection


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"
MAX_RESULTS = 8
STOPWORDS = {
    "available",
    "a",
    "answer",
    "an",
    "and",
    "any",
    "are",
    "at",
    "best",
    "cheapest",
    "deals",
    "drink",
    "drunk",
    "find",
    "for",
    "give",
    "good",
    "highest",
    "i",
    "im",
    "is",
    "look",
    "looking",
    "market",
    "me",
    "my",
    "most",
    "now",
    "on",
    "only",
    "please",
    "price",
    "product",
    "rated",
    "recommend",
    "sale",
    "sell",
    "seller",
    "show",
    "single",
    "there",
    "the",
    "to",
    "top",
    "want",
    "what",
}
SYNONYMS = {
    "air fryer": "airfryer",
    "basic phone": "basic mobile",
    "ceiling fan": "ceilingfans",
    "dongle": "adapter",
    "ear buds": "earbuds",
    "ear phone": "earphones",
    "ear phones": "earphones",
    "earbud": "earbuds",
    "earbuds": "in ear",
    "egg boiler": "eggboilers",
    "fan heater": "fanheaters",
    "flash drive": "pendrive",
    "fridge": "refrigerator",
    "geyser": "water heater",
    "graphic tablet": "graphictablets",
    "hard disk bag": "harddiskbags",
    "hdmi cable": "hdmi cables",
    "hot water kettle": "electric kettle",
    "immersion rod": "immersionrods",
    "induction stove": "inductioncooktop",
    "ipad case": "cases",
    "iron box": "iron",
    "juice mixer": "juicer mixer grinder",
    "keyboard mouse combo": "keyboard mouse sets",
    "keyboard mouse set": "keyboard mouse sets",
    "laptop desk": "lapdesks",
    "lint remover": "lintshavers",
    "memory card": "microsd",
    "mouse combo": "keyboard mouse sets",
    "pen drive": "pendrive",
    "portable charger": "powerbank",
    "power bank": "powerbank",
    "remote": "remotecontrols",
    "router dongle": "wireless usb adapter",
    "sandwich maker": "sandwichmakers",
    "sd card": "microsd",
    "smart phone": "smartphone",
    "smart watch": "smartwatch",
    "steam iron": "steamirons",
    "tv remote": "remotecontrols",
    "smart tv": "smart television",
    "smart tvs": "smart television",
    "type c cable": "usb c cable",
    "usb adapter": "wireless usb adapter",
    "tv": "television",
    "tvs": "television",
    "usb-c": "usb c",
    "type-c": "usb c",
    "type c": "usb c",
    "lightning cable": "lightning",
    "water purifier": "water filters purifiers",
    "wall charger": "wallchargers",
    "washing basket": "laundrybaskets",
    "wifi adapter": "wireless usb adapter",
    "wifi dongle": "wireless usb adapter",
    "wifi router": "routers",
    "wireless mouse": "mice",
    "charger cable": "cable",
}
SORT_MODE_PATTERNS = {
    "highest_rated": (
        "highest rated",
        "top rated",
        "best rated",
        "highest rating",
    ),
    "cheapest": (
        "cheapest",
        "lowest price",
        "most affordable",
        "least expensive",
    ),
    "biggest_discount": (
        "biggest discount",
        "best discount",
        "largest discount",
        "best deal",
        "good deal",
        "good deals",
    ),
    "most_expensive": (
        "most expensive",
        "highest price",
        "highest priced",
        "priciest",
    ),
}


@dataclass(frozen=True)
class QueryIntent:
    keywords: list[str]
    sort_mode: str
    result_limit: int


def _normalize_text(value: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    text = text.lower()
    for source, target in SYNONYMS.items():
        text = text.replace(source, target)
    text = text.replace("&", " and ")
    text = text.replace("|", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_keywords(message: str) -> list[str]:
    normalized = _normalize_text(message)
    keywords: list[str] = []
    for token in normalized.split():
        if token in STOPWORDS or len(token) < 2:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords


def _detect_result_limit(message: str) -> int:
    normalized = _normalize_text(message)
    match = re.search(r"\bonly\s+(\d+)\b", normalized)
    if match:
        return max(1, min(int(match.group(1)), MAX_RESULTS))

    match = re.search(r"\btop\s+(\d+)\b", normalized)
    if match:
        return max(1, min(int(match.group(1)), MAX_RESULTS))

    if any(
        phrase in normalized
        for phrase in (
            "only 1",
            "only one",
            "just one",
            "single answer",
            "one answer",
            "single most",
            "single best",
            "single cheapest",
            "single highest",
        )
    ):
        return 1

    return MAX_RESULTS


def _detect_sort_mode(message: str, mode: str) -> str:
    normalized = _normalize_text(message)
    for sort_mode, patterns in SORT_MODE_PATTERNS.items():
        if any(pattern in normalized for pattern in patterns):
            return sort_mode
    if mode == "seller":
        return "seller_price"
    return "best_match"


def _parse_query_intent(mode: str, message: str) -> QueryIntent:
    return QueryIntent(
        keywords=_extract_keywords(message),
        sort_mode=_detect_sort_mode(message, mode),
        result_limit=_detect_result_limit(message),
    )


def _build_search_text(dataframe: pd.DataFrame) -> pd.Series:
    return (
        dataframe["product_name"].fillna("")
        + " "
        + dataframe["category"].fillna("")
        + " "
        + dataframe["about_product"].fillna("")
    ).map(_normalize_text)


@lru_cache(maxsize=1)
def load_products_dataframe() -> pd.DataFrame:
    with get_connection() as connection:
        dataframe = pd.read_sql_query(
            """
            SELECT
                product_id,
                product_name,
                category,
                discounted_price_myr,
                actual_price_myr,
                discount_percentage,
                rating,
                rating_count,
                about_product,
                img_link,
                product_link
            FROM amazon_products
            """,
            connection,
        )

    dataframe["discounted_price_myr"] = pd.to_numeric(
        dataframe["discounted_price_myr"], errors="coerce"
    )
    dataframe["actual_price_myr"] = pd.to_numeric(
        dataframe["actual_price_myr"], errors="coerce"
    )
    dataframe["discount_percentage"] = pd.to_numeric(
        dataframe["discount_percentage"], errors="coerce"
    ).fillna(0.0)
    dataframe["rating"] = pd.to_numeric(dataframe["rating"], errors="coerce").fillna(0.0)
    dataframe["rating_count"] = pd.to_numeric(
        dataframe["rating_count"], errors="coerce"
    ).fillna(0)

    dataframe["search_text"] = _build_search_text(dataframe)
    dataframe["deal_score"] = (
        dataframe["discount_percentage"] * 0.45
        + dataframe["rating"].clip(lower=0, upper=5).div(5) * 0.35
        + dataframe["rating_count"].clip(lower=0).map(lambda value: min(value, 50000))
        / 50000
        * 0.20
    )
    return dataframe


def refresh_products_dataframe() -> None:
    load_products_dataframe.cache_clear()


def _apply_sort_mode(dataframe: pd.DataFrame, sort_mode: str) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe

    if sort_mode == "highest_rated":
        return dataframe.sort_values(
            ["rating", "rating_count", "discount_percentage", "discounted_price_myr"],
            ascending=[False, False, False, True],
        )
    if sort_mode == "cheapest":
        return dataframe.sort_values(
            ["discounted_price_myr", "rating", "rating_count"],
            ascending=[True, False, False],
            na_position="last",
        )
    if sort_mode == "biggest_discount":
        return dataframe.sort_values(
            ["discount_percentage", "rating", "rating_count"],
            ascending=[False, False, False],
        )
    if sort_mode == "most_expensive":
        return dataframe.sort_values(
            ["discounted_price_myr", "rating", "rating_count"],
            ascending=[False, False, False],
            na_position="last",
        )
    if sort_mode == "seller_price":
        return dataframe.sort_values(
            ["match_score", "rating", "rating_count", "discounted_price_myr"],
            ascending=[False, False, False, True],
            na_position="last",
        )
    return dataframe.sort_values(
        ["match_score", "deal_score", "rating", "rating_count"],
        ascending=[False, False, False, False],
    )


def _score_matches(dataframe: pd.DataFrame, intent: QueryIntent, seller_mode: bool) -> pd.DataFrame:
    if not intent.keywords:
        ranked = dataframe.copy()
        ranked["keyword_score"] = 0.0
        ranked["match_score"] = ranked["deal_score"]
        return _apply_sort_mode(ranked, intent.sort_mode)

    ranked = dataframe.copy()
    ranked["keyword_score"] = ranked["search_text"].map(
        lambda value: sum(1 for keyword in intent.keywords if keyword in value)
        / len(intent.keywords)
    )
    ranked = ranked[ranked["keyword_score"] > 0]
    if ranked.empty:
        return ranked

    if seller_mode:
        ranked["match_score"] = (
            ranked["keyword_score"] * 0.65
            + ranked["rating"].clip(lower=0, upper=5).div(5) * 0.20
            + (1 - ranked["discount_percentage"].clip(lower=0, upper=1)) * 0.15
        )
    else:
        ranked["match_score"] = ranked["keyword_score"] * 0.55 + ranked["deal_score"] * 0.45

    return _apply_sort_mode(ranked, intent.sort_mode)


def _serialize_products(dataframe: pd.DataFrame, limit: int) -> list[dict[str, object]]:
    if dataframe.empty:
        return []

    columns = [
        "product_id",
        "product_name",
        "category",
        "discounted_price_myr",
        "actual_price_myr",
        "discount_percentage",
        "rating",
        "rating_count",
        "img_link",
        "product_link",
        "match_score",
    ]
    records = dataframe.loc[:, columns].head(limit).to_dict(orient="records")
    products: list[dict[str, object]] = []
    for record in records:
        products.append(
            {
                **record,
                "discounted_price_myr": _round_or_none(record["discounted_price_myr"]),
                "actual_price_myr": _round_or_none(record["actual_price_myr"]),
                "discount_percentage": _round_or_none(record["discount_percentage"]),
                "rating": _round_or_none(record["rating"]),
                "rating_count": int(record["rating_count"] or 0),
                "match_score": _round_or_none(record["match_score"]),
            }
        )
    return products


def _round_or_none(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def _confidence_from_match_count(match_count: int) -> str:
    if match_count >= 15:
        return "high"
    if match_count >= 5:
        return "medium"
    return "low"


def _build_ranked_summary(
    mode: str,
    sort_mode: str,
    products: list[dict[str, object]],
    match_count: int,
) -> str:
    if not products:
        return ""

    best = products[0]
    product_name = best["product_name"]
    price = best["discounted_price_myr"]
    rating = best["rating"]
    discount = best["discount_percentage"]

    if sort_mode == "highest_rated":
        return (
            f"The highest-rated matching product is {product_name} with a rating of "
            f"{rating} from {best['rating_count']} reviews, priced at MYR {price}."
        )
    if sort_mode == "cheapest":
        return (
            f"The cheapest matching product is {product_name} at MYR {price}. "
            f"It is rated {rating} and I found {match_count} matching listings."
        )
    if sort_mode == "most_expensive":
        return (
            f"The most expensive matching product is {product_name} at MYR {price}. "
            f"It has a rating of {rating} and a listed discount of {discount}."
        )
    if sort_mode == "biggest_discount":
        return (
            f"The strongest discount among the matches is on {product_name}, priced at "
            f"MYR {price} with a discount level of {discount}."
        )
    if mode == "buyer":
        return (
            f"I found {match_count} matching products. The strongest current option is "
            f"{product_name} at MYR {price}, with a rating of {rating} and discount "
            f"score of {discount}."
        )
    return ""


def _build_seller_summary(
    message: str,
    products: list[dict[str, object]],
    match_count: int,
    sort_mode: str,
) -> str:
    if not products:
        return (
            f"I could not find strong comparables in the dataset for '{message}'. "
            "Try being more specific about the product type, brand, or connector."
        )

    ranked_summary = _build_ranked_summary("seller", sort_mode, products, match_count)
    if ranked_summary:
        return ranked_summary

    prices = [product["discounted_price_myr"] for product in products if product["discounted_price_myr"]]
    if not prices:
        return (
            "I found comparable products, but they do not have enough price data "
            "for a confident pricing range."
        )

    low_price = min(prices)
    high_price = max(prices)
    mid_price = round(sum(prices) / len(prices), 2)
    return (
        f"Based on {match_count} comparable listings in the dataset, a reasonable "
        f"sale price is around MYR {mid_price} with a likely range of MYR "
        f"{low_price:.2f} to MYR {high_price:.2f}."
    )


def _build_buyer_summary(
    message: str,
    products: list[dict[str, object]],
    match_count: int,
    sort_mode: str,
) -> str:
    if not products:
        return (
            f"I could not find strong matches in the dataset for '{message}'. "
            "Try naming the product type or brand more directly."
        )

    ranked_summary = _build_ranked_summary("buyer", sort_mode, products, match_count)
    if ranked_summary:
        return ranked_summary

    best = products[0]
    return (
        f"I found {match_count} matching products. The strongest current option is "
        f"{best['product_name']} at MYR {best['discounted_price_myr']}, with a "
        f"rating of {best['rating']} and discount score of {best['discount_percentage']}."
    )


def _build_prompt(
    mode: str,
    message: str,
    intent: QueryIntent,
    products: list[dict[str, object]],
    deterministic_summary: str,
) -> str:
    instruction = (
        "You are a deal-finding assistant for Amazon sale data in MYR. "
        "Use only the retrieved evidence below as factual grounding. "
        "You may add light shopping or pricing advice, but do not invent products, "
        "prices, ratings, or discounts. If evidence is sparse, say so clearly."
    )
    if mode == "seller":
        instruction += (
            " The user is a seller. Recommend a pricing range and briefly explain "
            "how the comparable products support it."
        )
    else:
        instruction += (
            " The user is a buyer. Recommend the best deals first and explain why "
            "they look attractive."
        )

    evidence = json.dumps(products, ensure_ascii=True)
    response_instruction = "Respond in 2 short paragraphs. Mention prices in MYR."
    if intent.result_limit == 1:
        response_instruction = (
            "Respond with exactly 1 recommendation. Keep it concise and mention prices in MYR."
        )
    return (
        f"{instruction}\n\n"
        f"User mode: {mode}\n"
        f"User message: {message}\n"
        f"Extracted keywords: {', '.join(intent.keywords) if intent.keywords else 'none'}\n"
        f"Sort intent: {intent.sort_mode}\n"
        f"Requested result count: {intent.result_limit}\n"
        f"Deterministic backend summary: {deterministic_summary}\n"
        f"Retrieved products: {evidence}\n\n"
        f"{response_instruction}"
    )


def _generate_gemini_response(prompt: str) -> tuple[str | None, str | None]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None, "GEMINI_API_KEY is not configured"

    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        text = getattr(response, "text", None)
        if text:
            return text.strip(), None
        return None, "Gemini returned an empty response"
    except Exception as exc:  # pragma: no cover - external API variability
        return None, str(exc)


def run_assistant_query(mode: str, message: str) -> dict[str, object]:
    dataframe = load_products_dataframe()
    intent = _parse_query_intent(mode, message)
    ranked = _score_matches(dataframe, intent, seller_mode=mode == "seller")
    products = _serialize_products(ranked, intent.result_limit)
    match_count = int(len(ranked))
    confidence = _confidence_from_match_count(match_count)

    if mode == "seller":
        deterministic_summary = _build_seller_summary(
            message, products, match_count, intent.sort_mode
        )
    else:
        deterministic_summary = _build_buyer_summary(
            message, products, match_count, intent.sort_mode
        )

    prompt = _build_prompt(mode, message, intent, products, deterministic_summary)
    llm_answer, llm_error = _generate_gemini_response(prompt)

    return {
        "answer": llm_answer or deterministic_summary,
        "products": products,
        "metadata": {
            "mode": mode,
            "query_terms": intent.keywords,
            "matched_count": match_count,
            "confidence": confidence,
            "llm_used": llm_answer is not None,
            "llm_error": llm_error,
            "database_path": str(Path(DB_PATH).resolve()),
        },
    }
