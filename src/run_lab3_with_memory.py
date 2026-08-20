"""Lab 3 확장 — Memory + Gateway 연결.

Lab 2 에서 Memory 에 저장한 사용자 프로필(UserPreference)을
Lab 3 의 recommend 도구에 자동 주입하는 예시입니다.
피부타입을 매 번 다시 말하지 않아도 개인화 추천이 동작하게 됩니다.

사용법 (src/ 에서):
  python run_lab3_with_memory.py                         # 기본 질문 "보습 세럼 추천해줘"
  python run_lab3_with_memory.py "그 중 재고 있는 거"   # 직접 질문
  python run_lab3_with_memory.py --user alice "..."     # 다른 사용자 id

선행 조건:
  - Lab 2 의 python run_lab2.py seed 로 프로필이 저장돼 있어야 함
  - 환경변수: AGENTCORE_MEMORY_ID, AGENTCORE_GATEWAY_URL, AWS_REGION
"""
from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

from agents.recommend_agent import ask_recommend_agent
from memory import get_memory_client, get_memory_id

load_dotenv()

DEFAULT_USER = "demo-user"
DEFAULT_QUESTION = "보습 세럼 추천해줘"


def _parse(raw: str) -> str:
    try:
        obj = json.loads(raw)
        return obj.get("preference") or obj.get("context") or raw
    except Exception:
        return raw


def fetch_preferences(user_id: str) -> list[str]:
    """USER_PREFERENCE 네임스페이스에서 이 사용자의 선호만 조회."""
    client = get_memory_client()
    mem_id = get_memory_id()
    try:
        records = client.retrieve_memories(
            memory_id=mem_id,
            namespace=f"/preferences/{user_id}/",
            query="피부타입 선호",
        )
    except Exception as e:
        print(f"[경고] Memory 조회 실패: {e}")
        return []
    return [_parse(r["content"]["text"]) for r in records]


def run_with_memory(user_id: str, user_msg: str) -> str:
    prefs = fetch_preferences(user_id)

    print(f"[사용자] {user_id}")
    if prefs:
        print("[Memory 에서 불러온 프로필]")
        for p in prefs:
            print(f"  - {p}")
    else:
        print("[프로필 없음] Lab 2 의 seed 를 먼저 실행하세요.")
    print()

    profile_block = "\n".join(f"- {p}" for p in prefs) if prefs else "- (저장된 선호 없음)"
    augmented = (
        f"[사용자 프로필]\n{profile_block}\n\n"
        f"[사용자 질문]\n{user_msg}\n\n"
        "위 프로필을 recommend_products 도구의 skin_type·concerns 인자에 반영해 주세요."
    )

    print(f"[질문]\n{user_msg}\n")
    print("[도구 호출 내역]")
    response = ask_recommend_agent(augmented, verbose=True)
    print(f"\n[답변]\n{response}\n")
    return response


def main() -> None:
    args = sys.argv[1:]
    user = DEFAULT_USER
    if args and args[0] == "--user":
        if len(args) < 2:
            print("usage: --user <user_id> [질문]")
            sys.exit(1)
        user = args[1]
        args = args[2:]
    question = " ".join(args) if args else DEFAULT_QUESTION
    run_with_memory(user, question)


if __name__ == "__main__":
    main()
