"""
공유 상품 데이터 로더 + 스키마 정의.

워크샵 범위: 인메모리 dict 반환. 실제 서비스에서는
상품 DB(DynamoDB, RDS 등) 또는 내부 상품 API로 교체합니다.
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

DATA_FILE_ENV = "BEAUTY_PRODUCTS_FILE"
DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "beauty_products.jsonl"


def load_products() -> list[dict]:
    path = Path(os.environ.get(DATA_FILE_ENV, DEFAULT_DATA_PATH))
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def filter_by_price(products: list[dict], price_max: int | None) -> list[dict]:
    if price_max is None:
        return products
    return [p for p in products if p["price_krw"] <= price_max]


def filter_by_category(products: list[dict], category: str | None) -> list[dict]:
    if not category:
        return products
    needle = category.lower()
    return [p for p in products if needle in p["category"].lower()]


def filter_by_skin_type(products: list[dict], skin_type: str | None) -> list[dict]:
    if not skin_type:
        return products
    return [
        p for p in products
        if skin_type in p.get("skin_type", []) or "모든 피부" in p.get("skin_type", [])
    ]


def match_query(product: dict, query: str) -> bool:
    if not query:
        return True
    q = query.lower()
    haystack = " ".join([
        product["name"], product["brand"], product["category"],
        " ".join(product.get("key_ingredients", [])),
        " ".join(product.get("highlights", [])),
        product.get("review_summary", ""),
    ]).lower()
    return all(token in haystack for token in q.split())


def compact(product: dict) -> dict:
    """LLM context 낭비 방지: 핵심 필드만 반환."""
    return {
        "product_id": product["product_id"],
        "brand": product["brand"],
        "name": product["name"],
        "category": product["category"],
        "price_krw": product["price_krw"],
        "highlights": product.get("highlights", []),
        "average_rating": product.get("average_rating"),
    }


def deterministic_stock(product_id: str) -> dict:
    """재고는 상품 ID 해시로 결정 → 워크샵에서 재현 가능."""
    rnd = random.Random(product_id)
    available = rnd.random() > 0.15
    eta = rnd.choice(["오늘 출고", "내일 도착", "2~3일 이내 도착"])
    return {
        "product_id": product_id,
        "available": available,
        "eta": eta if available else None,
        "note": None if available else "현재 품절, 재입고 알림 신청 가능",
    }
