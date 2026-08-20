"""로컬 smoke test — 4개 Lambda가 의도한 응답을 주는지 빠르게 확인."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from product_search.app import handler as search
from recommend_products.app import handler as recommend
from check_stock.app import handler as stock
from get_promotion.app import handler as promo


def run(label, result):
    body = json.loads(result["body"])
    print(f"\n=== {label} (status={result['statusCode']}) ===")
    print(json.dumps(body, ensure_ascii=False, indent=2)[:600])


run("search: 비건 크림 3만원 이하",
    search({"query": "비건 크림", "price_max": 30000}))

run("search: 카테고리=향수",
    search({"category": "향수"}))

run("recommend: 건성 + 보습",
    recommend({"skin_type": "건성", "concerns": ["보습"]}))

run("recommend: 민감성 + 진정",
    recommend({"skin_type": "민감성", "concerns": ["진정"]}))

run("stock: WHOO-00101",
    stock({"product_id": "WHOO-00101"}))

run("stock: unknown",
    stock({"product_id": "WHOO-99999"}))

run("promo: 카테고리=스킨케어",
    promo({"category": "스킨케어"}))

run("promo: product_id=WHOO-00101 (더후 브랜드 프로모션 매칭 기대)",
    promo({"product_id": "WHOO-00101"}))
