#!/usr/bin/env python3
"""Bedrock KB retrieve 결과를 사람이 읽기 좋게 요약.

Lab 0 의 CLI 출력이 escape 된 한 줄 JSON 으로 보기 어려워
같은 쿼리를 이 스크립트로 돌리면 상품 단위로 정돈되어 출력됩니다.

Usage:
  KB_ID=<kb> AWS_REGION=us-east-1 \
    python3 scripts/pretty-retrieve.py "건성 피부에 좋은 보습크림"
  KB_ID=<kb> AWS_REGION=us-east-1 \
    python3 scripts/pretty-retrieve.py "천기단 복합 성분" 5
"""
from __future__ import annotations

import json
import os
import sys

import boto3


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: pretty-retrieve.py <query> [num_results=3]", file=sys.stderr)
        sys.exit(1)
    query = sys.argv[1]
    num = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    kb_id = os.environ.get("KB_ID")
    region = os.environ.get("AWS_REGION", "us-east-1")
    if not kb_id:
        print("[ERROR] KB_ID 환경변수가 설정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)

    client = boto3.client("bedrock-agent-runtime", region_name=region)
    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": num}
        },
    )

    print(f"Query: \"{query}\"")
    print(f"KB: {kb_id}  |  Top {num} results")
    print()

    results = resp.get("retrievalResults", [])
    for i, r in enumerate(results, 1):
        raw = r["content"]["text"]
        score = r.get("score", 0)
        try:
            obj = json.loads(raw)
            print(f"=== [{i}] 관련도 {score:.3f} ===")
            print(f"  상품ID : {obj.get('product_id', '-')}")
            print(f"  이름   : {obj.get('name', '-')}  ({obj.get('brand', '-')})")
            print(f"  카테고리: {obj.get('category', '-')}")
            skin = obj.get("skin_type", [])
            print(f"  피부타입: {', '.join(skin) if skin else '-'}")
            price = obj.get("price_krw")
            print(f"  가격   : {price:,}원" if price else "  가격   : -")
            ing = obj.get("key_ingredients", [])
            print(f"  성분   : {', '.join(ing) if ing else '-'}")
            hl = obj.get("highlights", [])
            print(f"  특징   : {' / '.join(hl) if hl else '-'}")
            print(f"  평점   : {obj.get('average_rating', '-')}")
            print()
        except Exception:
            print(f"=== [{i}] 관련도 {score:.3f} (파싱 실패) ===")
            print(f"  {raw[:200]}...")
            print()

    if not results:
        print("  (결과 없음 — ingestion 이 아직 진행 중일 수 있습니다)")


if __name__ == "__main__":
    main()
