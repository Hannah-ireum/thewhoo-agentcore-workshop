#!/usr/bin/env python3
"""TheWhooMemory 를 지우고 다시 만들 때 사용하는 정리 스크립트.

이전 실행에서 타입이 잘못 등록된 strategy 가 남아 있을 때 사용합니다.
Memory 를 통째로 삭제하므로 안에 쌓인 단기/장기 메모리가 같이 사라집니다.

Usage:
  python3 scripts/cleanup-memory.py
"""

from __future__ import annotations

import os
import sys

from bedrock_agentcore.memory import MemoryClient


MEMORY_NAME = "TheWhooMemory"
REGION = os.environ.get("AWS_REGION", "us-east-1")


def main() -> None:
    client = MemoryClient(region_name=REGION)

    memories = client.list_memories()
    target = next(
        (m for m in memories if (m.get("name") or m.get("id", "")).startswith(MEMORY_NAME)),
        None,
    )
    if not target:
        print(f"[정보] {MEMORY_NAME} 이(가) 이미 없습니다.")
        return

    memory_id = target.get("id") or target.get("memoryId")
    print(f"[주의] 다음 Memory 를 삭제합니다: {memory_id}")
    ans = input("정말 삭제하시겠습니까? (yes / no): ").strip().lower()
    if ans != "yes":
        print("취소됨.")
        sys.exit(0)

    print("삭제 중… (최대 1~2분)")
    client.delete_memory_and_wait(memory_id=memory_id)
    print(f"✓ 삭제 완료: {memory_id}")
    print()
    print("이제 python3 scripts/create-memory.py 를 다시 실행하세요.")


if __name__ == "__main__":
    main()
