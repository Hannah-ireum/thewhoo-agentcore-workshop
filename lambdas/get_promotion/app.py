"""
get_promotion Mock Lambda

현재 진행 중인 프로모션(할인/증정/쿠폰) 조회. 카테고리 또는
상품 ID로 필터링 가능. 워크샵에서는 고정 프로모션 세트를 반환합니다.
실서비스에서는 프로모션 엔진 API로 교체.

기간(period)은 호출 시점 기준으로 계산합니다. 고정 날짜를 박아 두면
워크샵을 나중에 재실행할 때 "진행 중" 이라면서 이미 끝난 날짜를
안내하게 되고, LLM 이 이 모순을 답변에 그대로 노출합니다.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from _shared.products import load_products


def _period(start_offset: int, end_offset: int) -> str:
    """오늘 기준 상대 기간 문자열. 예: _period(-3, 11) → 3일 전 시작, 11일 후 종료."""
    today = date.today()
    start = today + timedelta(days=start_offset)
    end = today + timedelta(days=end_offset)
    return f"{start.isoformat()} ~ {end.isoformat()}"


def _promotions() -> list[dict]:
    """항상 '오늘' 이 기간 안에 들어오는 프로모션 세트."""
    return [
        {
            "promotion_id": "P-SKINCARE-10",
            "title": "더후 스킨케어 10% 할인",
            "applies_to": {"type": "category_prefix", "value": "스킨케어"},
            "benefit": "10% 할인",
            "period": _period(-3, 11),
        },
        {
            "promotion_id": "P-PERFUME-MINI",
            "title": "향수 2만원 이상 구매 시 미니어처 증정",
            "applies_to": {"type": "category_prefix", "value": "향수"},
            "benefit": "미니어처 5ml 증정",
            "period": _period(-7, 7),
        },
        {
            "promotion_id": "P-WHOO-ESSENCE",
            "title": "더후 천기단 크림 구매 시 에센스 증정",
            "applies_to": {"type": "brand", "value": "더후"},
            "benefit": "천기단 화현 에센스 10ml 증정",
            "period": _period(-1, 6),
        },
        {
            "promotion_id": "P-HAIR-COUPON",
            "title": "헤어 카테고리 리뷰 작성 시 5천원 쿠폰",
            "applies_to": {"type": "category_prefix", "value": "헤어"},
            "benefit": "리뷰 작성 시 5,000원 쿠폰",
            "period": "상시",
        },
    ]


def handler(event: dict, _context: Any = None) -> dict:
    params = _extract_params(event)
    product_id = params.get("product_id")
    category = params.get("category")

    applicable = []
    if product_id:
        applicable = _match_by_product(product_id)
    elif category:
        applicable = _match_by_category(category)
    else:
        applicable = _promotions()

    return _ok({
        "product_id": product_id,
        "category": category,
        "count": len(applicable),
        "promotions": applicable,
    })


def _match_by_product(product_id: str) -> list[dict]:
    products = {p["product_id"]: p for p in load_products()}
    product = products.get(product_id)
    if not product:
        return []
    return [p for p in _promotions() if _applies(p, product)]


def _match_by_category(category: str) -> list[dict]:
    return [
        p for p in _promotions()
        if p["applies_to"]["type"] == "category_prefix"
        and p["applies_to"]["value"].lower() in category.lower()
    ]


def _applies(promotion: dict, product: dict) -> bool:
    spec = promotion["applies_to"]
    if spec["type"] == "category_prefix":
        return product["category"].startswith(spec["value"])
    if spec["type"] == "brand":
        return product["brand"] == spec["value"]
    return False


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
