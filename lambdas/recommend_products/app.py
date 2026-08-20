"""
recommend_products Mock Lambda

사용자 피부타입/관심사(concerns) 기반 개인화 추천입니다.
product_search와 달리 프로필을 직접 받아 필터링/랭킹 근거를
함께 반환합니다 (reason 필드).
"""
from __future__ import annotations

import json
from typing import Any

from _shared.products import compact, filter_by_skin_type, load_products

MAX_RESULTS = 4

CONCERN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "보습": ("히알루론산", "세라마이드", "보습", "판테놀"),
    "진정": ("마데카소사이드", "시카", "병풀", "진정"),
    "미백": ("비타민C", "나이아신아마이드", "브라이트닝", "톤"),
    "주름": ("레티놀", "콜라겐", "펩타이드", "탄력"),
    "모공": ("클레이", "살리실산", "모공"),
    "자외선": ("SPF", "자외선", "선"),
}


def handler(event: dict, _context: Any = None) -> dict:
    params = _extract_params(event)
    skin_type = params.get("skin_type")
    concerns = params.get("concerns") or []
    if isinstance(concerns, str):
        concerns = [c.strip() for c in concerns.split(",") if c.strip()]

    items = load_products()
    items = filter_by_skin_type(items, skin_type)

    scored = []
    for p in items:
        score, reasons = _score(p, concerns)
        if score > 0 or not concerns:
            scored.append((score, p, reasons))

    scored.sort(key=lambda t: (-t[0], -t[1].get("average_rating", 0)))
    top = scored[:MAX_RESULTS]

    products = [
        {**compact(p), "reason": _format_reason(reasons, skin_type)}
        for _score, p, reasons in top
    ]
    return _ok({
        "skin_type": skin_type,
        "concerns": concerns,
        "count": len(products),
        "products": products,
    })


def _score(product: dict, concerns: list[str]) -> tuple[int, list[str]]:
    if not concerns:
        return (0, [])
    ingredients = " ".join(product.get("key_ingredients", []))
    highlights = " ".join(product.get("highlights", []))
    haystack = (ingredients + " " + highlights + " " + product["name"]).lower()
    matched = []
    score = 0
    for concern in concerns:
        keywords = CONCERN_KEYWORDS.get(concern, (concern,))
        for kw in keywords:
            if kw.lower() in haystack:
                score += 1
                matched.append(concern)
                break
    return (score, list(dict.fromkeys(matched)))


def _format_reason(matched_concerns: list[str], skin_type: str | None) -> str:
    parts = []
    if skin_type:
        parts.append(f"{skin_type} 피부에 적합")
    if matched_concerns:
        parts.append(f"{'/'.join(matched_concerns)} 고민에 도움되는 성분 포함")
    return ", ".join(parts) or "인기 상품"


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
