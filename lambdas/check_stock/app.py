"""
check_stock Mock Lambda

상품 ID 기반 재고·배송 예정 조회. 실서비스에서는 OMS/물류 시스템
API로 교체. 워크샵에서는 product_id 해시 기반 결정적 응답.
"""
from __future__ import annotations

import json
from typing import Any

from _shared.products import deterministic_stock, load_products


def handler(event: dict, _context: Any = None) -> dict:
    params = _extract_params(event)
    product_id = params.get("product_id")
    if not product_id:
        return _err(400, "product_id is required")

    products = {p["product_id"]: p for p in load_products()}
    if product_id not in products:
        return _err(404, f"unknown product_id: {product_id}")

    stock = deterministic_stock(product_id)
    product = products[product_id]
    stock["brand"] = product["brand"]
    stock["name"] = product["name"]
    return _ok(stock)


def _extract_params(event: dict) -> dict:
    if "queryStringParameters" in event and event["queryStringParameters"]:
        return event["queryStringParameters"]
    if "body" in event and isinstance(event["body"], str):
        try:
            return json.loads(event["body"])
        except json.JSONDecodeError:
            return {}
    return event


def _ok(body: dict) -> dict:
    return {"statusCode": 200, "body": json.dumps(body, ensure_ascii=False)}


def _err(code: int, message: str) -> dict:
    return {
        "statusCode": code,
        "body": json.dumps({"error": message}, ensure_ascii=False),
    }
