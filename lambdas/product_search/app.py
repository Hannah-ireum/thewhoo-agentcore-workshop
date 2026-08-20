"""
product_search Mock Lambda

키워드/자연어 쿼리 + 카테고리 + 가격 상한으로 상품을 검색합니다.
사용자 프로필을 반영하지 않는 "범용 키워드 검색"이 목적입니다
(프로필 반영 검색은 recommend_products 툴이 담당).

워크샵용 Mock: 인메모리 JSONL 기반. 실서비스에서는
사내 상품 검색 API 또는 검색 엔진 쿼리로 교체.
"""
from __future__ import annotations

import json
from typing import Any

from _shared.products import (
    compact, filter_by_category, filter_by_price, load_products, match_query,
)

MAX_RESULTS = 5


def handler(event: dict, _context: Any = None) -> dict:
    params = _extract_params(event)
    query = params.get("query") or ""
    category = params.get("category")
    price_max = _to_int(params.get("price_max"))

    items = load_products()
    items = filter_by_category(items, category)
    items = filter_by_price(items, price_max)
    items = [p for p in items if match_query(p, query)]
    items.sort(key=lambda p: (-p.get("average_rating", 0), p["price_krw"]))
    results = [compact(p) for p in items[:MAX_RESULTS]]

    return _ok({
        "query": query,
        "category": category,
        "price_max": price_max,
        "count": len(results),
        "products": results,
    })


def _extract_params(event: dict) -> dict:
    # API Gateway proxy (GET): queryStringParameters
    if "queryStringParameters" in event and event["queryStringParameters"]:
        return event["queryStringParameters"]
    # API Gateway proxy (POST) or MCP: body JSON
    if "body" in event and isinstance(event["body"], str):
        try:
            return json.loads(event["body"])
        except json.JSONDecodeError:
            return {}
    # Direct Lambda invoke (test / smoke_test)
    return event


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ok(body: dict) -> dict:
    return {"statusCode": 200, "body": json.dumps(body, ensure_ascii=False)}
