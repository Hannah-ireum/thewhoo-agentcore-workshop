#!/usr/bin/env python3
"""Lab 5 보조 — Bedrock prompt caching 직접 검증.

같은 system prompt 로 Bedrock Converse 를 2 회 호출해
cacheWriteInputTokens (1회차) → cacheReadInputTokens (2회차) 가
잡히는지 확인합니다.

사용법:
  python3 scripts/test-prompt-cache.py
  python3 scripts/test-prompt-cache.py --model haiku    # default
  python3 scripts/test-prompt-cache.py --model sonnet   # Sonnet 4.6 으로

요건 (공식 model card 기준):
  - Sonnet 4.6: prefix ≥ 1,024 tokens
  - Haiku 4.5 : prefix ≥ 4,096 tokens
스크립트가 모델별 최소 토큰 요건을 충족하도록 system prompt 를 자동 padding 합니다.

출처:
  https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html
  boto3 bedrock-runtime Converse API
"""
from __future__ import annotations

import argparse
import os
import sys

import boto3

MODELS = {
    # cache_min_tokens 는 모델 카드 기준 최소 prefix 토큰 수
    "haiku": {
        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "cache_min_tokens": 4096,
    },
    "sonnet": {
        "model_id": "us.anthropic.claude-sonnet-4-6",
        "cache_min_tokens": 1024,
    },
}


def build_padded_system_prompt(min_tokens: int) -> str:
    """대략 4 char ≈ 1 token 휴리스틱으로 충분히 긴 system prompt 생성."""
    base = (
        "당신은 더후(The History of Whoo) AI 챗봇 어시스턴트입니다. "
        "고객의 피부타입, 고민, 예산을 파악해 적합한 상품을 안내합니다. "
        "의료적 효능을 단정하지 않고, 한국어 존댓말로 간결하게 답합니다.\n\n"
    )
    filler = (
        "참고 가이드: 건성 피부에는 보습 강화 성분 (히알루론산, 세라마이드, 판테놀) "
        "을 우선 추천합니다. 민감성 피부에는 알코올 프리, 무향, 저자극 테스트 완료 제품을 "
        "권장합니다. 지성·복합성 피부에는 살리실산, 나이아신아마이드 같은 성분을 고려합니다. "
        "프로모션은 제품별로 진행 여부가 다르므로 매번 확인이 필요합니다.\n"
    )
    text = base
    # 4 char ≈ 1 token 가정 + 안전 여유 30%
    target_chars = int(min_tokens * 4 * 1.3)
    while len(text) < target_chars:
        text += filler
    return text


def converse(client, model_id: str, system_text: str, user_text: str) -> dict:
    """system 블록에 cachePoint 마커를 단 Converse 호출."""
    resp = client.converse(
        modelId=model_id,
        system=[
            {"text": system_text},
            {"cachePoint": {"type": "default"}},
        ],
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        inferenceConfig={"maxTokens": 200, "temperature": 0.3},
    )
    usage = resp.get("usage", {})
    return {
        "input": usage.get("inputTokens", 0),
        "output": usage.get("outputTokens", 0),
        "total": usage.get("totalTokens", 0),
        "cache_write": usage.get("cacheWriteInputTokens", 0),
        "cache_read": usage.get("cacheReadInputTokens", 0),
        "stop_reason": resp.get("stopReason"),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=list(MODELS), default="haiku")
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = p.parse_args()

    cfg = MODELS[args.model]
    client = boto3.client("bedrock-runtime", region_name=args.region)
    system_text = build_padded_system_prompt(cfg["cache_min_tokens"])
    print(f"model    : {cfg['model_id']}")
    print(f"region   : {args.region}")
    print(f"prefix   : 약 {len(system_text):,} chars (≥ {cfg['cache_min_tokens']:,} 토큰 목표)")
    print()

    questions = [
        "건성 피부에 좋은 보습 크림 한 가지만 추천해줘.",
        "그 상품의 핵심 성분 두 개만 짧게 알려줘.",
    ]

    for i, q in enumerate(questions, start=1):
        print(f"[{i}회차] question: {q}")
        try:
            usage = converse(client, cfg["model_id"], system_text, q)
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            sys.exit(1)
        print(
            "  inputTokens={input}  outputTokens={output}  "
            "cacheWriteInputTokens={cache_write}  cacheReadInputTokens={cache_read}".format(**usage)
        )
        print()

    print("해석 가이드:")
    print("  - 1회차에 cacheWriteInputTokens > 0 이면 캐시가 새로 생성됨 (정상).")
    print("  - 2회차에 cacheReadInputTokens > 0 이면 캐시 히트 (정상).")
    print("  - 2회차도 cacheWriteInputTokens 만 잡히면 prefix 가 변동했거나")
    print("    TTL(기본 5분) 안에 1회차 직후 호출이 아닌 경우.")


if __name__ == "__main__":
    main()
