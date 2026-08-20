#!/usr/bin/env python3
"""Lab 2 — AgentCore Memory 생성.

Memory 리소스 1개 + 4가지 장기 strategy 를 만듭니다.
  - Summary       : 세션 내 대화 요약
  - UserPreference: 사용자 선호 (피부타입, 브랜드, 가격대 등)
  - Semantic      : 도메인 사실·지식 (성분, 상품 속성)
  - Episodic      : 에피소드 (상담 흐름 — 의도, 액션, 결과)

이미 같은 이름의 Memory 가 있으면 재사용합니다.

Usage:
  python3 scripts/create-memory.py
"""

from __future__ import annotations

import os

import botocore.exceptions
from bedrock_agentcore.memory import MemoryClient


MEMORY_NAME = "TheWhooMemory"
REGION = os.environ.get("AWS_REGION", "us-east-1")


def main() -> None:
    print(f"Region: {REGION}")
    print()

    client = MemoryClient(region_name=REGION)

    print(f"[1/2] Memory 생성 또는 재사용: {MEMORY_NAME}")
    memory = client.create_or_get_memory(
        name=MEMORY_NAME,
        strategies=[],
        description="더후(The History of Whoo) 챗봇의 단기·장기 메모리",
    )
    memory_id = memory["id"]
    print(f"      ✓ MEMORY_ID = {memory_id}")

    # 이미 있는 strategy 타입을 먼저 조회 — AgentCore 는 타입별로 1개만 허용
    existing_types = set()
    for s in client.get_memory_strategies(memory_id):
        existing_types.add(s.get("type") or s.get("memoryStrategyType"))

    print(f"[2/2] strategy 등록 (타입별 1개, 이미 있으면 건너뜀)")

    def _add_builtin(fn, name: str, label: str, type_name: str, namespaces: list) -> None:
        """Summary / UserPreference / Semantic — SDK 편의 메서드 사용."""
        if type_name in existing_types:
            print(f"      ↺ {name} — 타입 '{type_name}' 이미 존재, 건너뜀")
            return
        try:
            fn(memory_id=memory_id, name=name, namespace_templates=namespaces)
            existing_types.add(type_name)
            print(f"      ✓ {name} — {label}")
        except botocore.exceptions.ClientError as e:
            if "already exist" in str(e):
                print(f"      ↺ {name} — 이미 존재, 건너뜀")
            else:
                raise

    def _add_episodic(name: str, label: str, namespaces: list, reflection_namespaces: list) -> None:
        """Episodic — SDK add_episodic_strategy_and_wait 사용."""
        if "EPISODIC" in existing_types:
            print(f"      ↺ {name} — 타입 'EPISODIC' 이미 존재, 건너뜀")
            return
        try:
            client.add_episodic_strategy_and_wait(
                memory_id=memory_id,
                name=name,
                namespace_templates=namespaces,
                reflection_namespace_templates=reflection_namespaces,
            )
            existing_types.add("EPISODIC")
            print(f"      ✓ {name} — {label}")
        except botocore.exceptions.ClientError as e:
            if "already exist" in str(e):
                print(f"      ↺ {name} — 이미 존재, 건너뜀")
            else:
                raise

    _add_builtin(
        client.add_summary_strategy_and_wait,
        name="SessionSummary",
        label="세션 내 대화 요약",
        type_name="SUMMARIZATION",
        namespaces=["/summaries/{actorId}/{sessionId}/"],
    )
    _add_builtin(
        client.add_user_preference_strategy_and_wait,
        name="UserPreference",
        label="피부타입 / 선호 브랜드 등",
        type_name="USER_PREFERENCE",
        namespaces=["/preferences/{actorId}/"],
    )
    _add_builtin(
        client.add_semantic_strategy_and_wait,
        name="SemanticFacts",
        label="도메인 사실·지식",
        type_name="SEMANTIC",
        namespaces=["/facts/{actorId}/"],
    )
    _add_episodic(
        name="EpisodicInteractions",
        label="상담 에피소드 (의도·액션·결과)",
        namespaces=["/episodes/{actorId}/{sessionId}/"],
        reflection_namespaces=["/episodes/{actorId}/"],
    )

    print()
    print("=" * 60)
    print(f"AGENTCORE_MEMORY_ID={memory_id}")
    print("=" * 60)
    print()
    print("다음 명령을 복사해 환경변수를 설정하세요:")
    print()
    print(f"  export AGENTCORE_MEMORY_ID={memory_id}")


if __name__ == "__main__":
    main()
