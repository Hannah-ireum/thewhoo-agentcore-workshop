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

import inspect
import os
import sys

import botocore.exceptions
from bedrock_agentcore.memory import MemoryClient


MEMORY_NAME = "TheWhooMemory"
REGION = os.environ.get("AWS_REGION", "us-east-1")


def _check_sdk() -> None:
    """bedrock-agentcore SDK 가 namespace_templates 를 받는지 먼저 확인.

    구버전(예: 1.1.2)의 add_*_strategy_and_wait 는 `namespaces` 만 받습니다.
    그대로 진행하면 Memory 리소스는 만들어진 뒤 strategy 등록 단계에서
      TypeError: ... got an unexpected keyword argument 'namespace_templates'
    로 죽습니다. **Memory 는 이미 생성된 상태**라 참가자는 "반쯤 만들어진"
    리소스를 손에 들고 원인을 모르게 됩니다. 그래서 먼저 막습니다.

    requirements.txt 는 bedrock-agentcore>=1.9.1 을 요구하고, 1.9.1 이상은
    namespace_templates 를 지원합니다 (실측 확인). venv 를 활성화하지 않아
    시스템/conda 의 구버전이 잡히는 경우가 대표적인 원인입니다.
    """
    sig = inspect.signature(MemoryClient.add_summary_strategy_and_wait)
    if "namespace_templates" in sig.parameters:
        return

    try:
        import importlib.metadata as md

        ver = md.version("bedrock-agentcore")
    except Exception:
        ver = "unknown"

    sys.exit(
        "[ERROR] bedrock-agentcore SDK 가 너무 낮습니다 "
        f"(설치됨: {ver}, 필요: >=1.9.1)\n"
        f"        MemoryClient 위치: {os.path.dirname(inspect.getfile(MemoryClient))}\n"
        "\n"
        "  이 버전은 strategy 등록 시 namespace_templates 를 받지 못해\n"
        "  Memory 만 만들어지고 strategy 등록에서 실패합니다.\n"
        "\n"
        "  대개 venv 를 활성화하지 않아 시스템 Python 이 잡힌 경우입니다:\n"
        "    cd ~/thewhoo-agentcore-workshop\n"
        "    source .venv/bin/activate\n"
        "    which python          # .venv/bin/python 이어야 정상\n"
        "\n"
        "  그래도 낮으면 다시 설치하세요:\n"
        "    pip install -r requirements.txt"
    )


def main() -> None:
    _check_sdk()
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
