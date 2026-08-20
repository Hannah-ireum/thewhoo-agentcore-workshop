#!/usr/bin/env python3
"""data/beauty_products.jsonl 에서 카테고리별 상품 개수 집계.

Lab 0 보조 — KB 에 어떤 카테고리 상품이 얼마나 들어갔는지 한눈에.
"""
from __future__ import annotations

import collections
import json
import os
import sys


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    jsonl = os.path.abspath(os.path.join(here, "..", "data", "beauty_products.jsonl"))
    if not os.path.exists(jsonl):
        print(f"파일 없음: {jsonl}", file=sys.stderr)
        sys.exit(1)

    counts = collections.Counter()
    total = 0
    with open(jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            top_category = obj["category"].split(" > ")[0]
            counts[top_category] += 1
            total += 1

    print(f"총 {total}개 상품")
    print()
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}개")


if __name__ == "__main__":
    main()
