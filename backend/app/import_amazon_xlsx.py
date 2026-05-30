import argparse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Iterable

import app.db as db_module
from app.db import get_connection, init_db


HEADER_TO_COLUMN = {
    "product_id": "product_id",
    "product_name": "product_name",
    "category": "category",
    "discounted_price_myr": "discounted_price_myr",
    "actual_price_myr": "actual_price_myr",
    "discount_percentage": "discount_percentage",
    "rating": "rating",
    "rating_count": "rating_count",
    "about_product": "about_product",
    "user_id": "user_id",
    "user_name": "user_name",
    "review_id": "review_id",
    "review_title": "review_title",
    "review_content": "review_content",
    "img_link": "img_link",
    "product_link": "product_link",
}

CELL_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
DEFAULT_WORKBOOK_PATH = Path(__file__).resolve().parents[2] / "data" / "amazon.xlsx"


def column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for ch in letters:
        index = (index * 26) + (ord(ch.upper()) - ord("A") + 1)
    return index - 1


def load_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []

    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("a:si", CELL_NS):
        text = "".join(node.text or "" for node in item.findall(".//a:t", CELL_NS))
        values.append(text)
    return values


def read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value = cell.find("a:v", CELL_NS)
    if value is None or value.text is None:
        return ""

    if cell.get("t") == "s":
        return shared_strings[int(value.text)]

    return value.text


def iter_sheet_rows(path: Path) -> Iterable[list[str]]:
    with zipfile.ZipFile(path) as workbook:
        shared_strings = load_shared_strings(workbook)
        sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        for row in sheet.findall("a:sheetData/a:row", CELL_NS):
            values: list[str] = []
            for cell in row.findall("a:c", CELL_NS):
                idx = column_index(cell.get("r", "A1"))
                while len(values) <= idx:
                    values.append("")
                values[idx] = read_cell_value(cell, shared_strings)
            yield values


def parse_float(value: str) -> float | None:
    text = value.strip().replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: str) -> int | None:
    text = value.strip().replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def clean_text(value: str) -> str | None:
    text = value.strip()
    return text or None


def build_record(headers: list[str], row: list[str], row_number: int) -> dict[str, object]:
    raw = {
        HEADER_TO_COLUMN[header]: row[index] if index < len(row) else ""
        for index, header in enumerate(headers)
        if header in HEADER_TO_COLUMN
    }
    return {
        "source_row_number": row_number,
        "product_id": clean_text(str(raw.get("product_id", ""))),
        "product_name": clean_text(str(raw.get("product_name", ""))),
        "category": clean_text(str(raw.get("category", ""))),
        "discounted_price_myr": parse_float(str(raw.get("discounted_price_myr", ""))),
        "actual_price_myr": parse_float(str(raw.get("actual_price_myr", ""))),
        "discount_percentage": parse_float(str(raw.get("discount_percentage", ""))),
        "rating": parse_float(str(raw.get("rating", ""))),
        "rating_count": parse_int(str(raw.get("rating_count", ""))),
        "about_product": clean_text(str(raw.get("about_product", ""))),
        "user_id": clean_text(str(raw.get("user_id", ""))),
        "user_name": clean_text(str(raw.get("user_name", ""))),
        "review_id": clean_text(str(raw.get("review_id", ""))),
        "review_title": clean_text(str(raw.get("review_title", ""))),
        "review_content": clean_text(str(raw.get("review_content", ""))),
        "img_link": clean_text(str(raw.get("img_link", ""))),
        "product_link": clean_text(str(raw.get("product_link", ""))),
    }


def import_workbook(workbook_path: Path, replace: bool) -> int:
    rows = iter_sheet_rows(workbook_path)
    headers = next(rows)
    count = 0

    init_db()
    with get_connection() as connection:
        if replace:
            connection.execute("DELETE FROM amazon_products")

        for row_number, row in enumerate(rows, start=2):
            record = build_record(headers, row, row_number)
            if not record["product_id"] or not record["product_name"]:
                continue

            connection.execute(
                """
                INSERT INTO amazon_products (
                    source_row_number,
                    product_id,
                    product_name,
                    category,
                    discounted_price_myr,
                    actual_price_myr,
                    discount_percentage,
                    rating,
                    rating_count,
                    about_product,
                    user_id,
                    user_name,
                    review_id,
                    review_title,
                    review_content,
                    img_link,
                    product_link
                ) VALUES (
                    :source_row_number,
                    :product_id,
                    :product_name,
                    :category,
                    :discounted_price_myr,
                    :actual_price_myr,
                    :discount_percentage,
                    :rating,
                    :rating_count,
                    :about_product,
                    :user_id,
                    :user_name,
                    :review_id,
                    :review_title,
                    :review_content,
                    :img_link,
                    :product_link
                )
                ON CONFLICT(source_row_number) DO UPDATE SET
                    product_id = excluded.product_id,
                    product_name = excluded.product_name,
                    category = excluded.category,
                    discounted_price_myr = excluded.discounted_price_myr,
                    actual_price_myr = excluded.actual_price_myr,
                    discount_percentage = excluded.discount_percentage,
                    rating = excluded.rating,
                    rating_count = excluded.rating_count,
                    about_product = excluded.about_product,
                    user_id = excluded.user_id,
                    user_name = excluded.user_name,
                    review_id = excluded.review_id,
                    review_title = excluded.review_title,
                    review_content = excluded.review_content,
                    img_link = excluded.img_link,
                    product_link = excluded.product_link,
                    imported_at = CURRENT_TIMESTAMP
                """,
                record,
            )
            count += 1

        connection.commit()

    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import data/amazon.xlsx into the SQLite amazon_products table."
    )
    parser.add_argument(
        "--xlsx",
        default=DEFAULT_WORKBOOK_PATH,
        type=Path,
        help="Path to the Excel workbook.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing amazon_products rows before importing.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        help=f"Override the SQLite database path (default: {db_module.DB_PATH}).",
    )
    args = parser.parse_args()

    workbook_path = args.xlsx.resolve()
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    if args.db is not None:
        db_module.DB_PATH = args.db.resolve()

    imported = import_workbook(workbook_path, replace=args.replace)
    print(f"Imported {imported} rows into {db_module.DB_PATH}")


if __name__ == "__main__":
    main()
