"""Lab 2 실행 파일 — Q&A Agent + AgentCore Memory.

사용법 (src/ 디렉토리에서):
  python run_lab2.py seed                   # 데모용 프로필 시드 (1회)
  python run_lab2.py ask "질문"             # 저장된 프로필 반영해 한 번 질문
  python run_lab2.py --chat [user_id]       # 대화형 REPL (기본 user: demo-user)

환경변수:
  KB_ID, AWS_REGION, AGENTCORE_MEMORY_ID
"""
from __future__ import annotations

import json
import os
import sys
import uuid

from dotenv import load_dotenv

from agents.qa_agent import create_qa_agent
from memory import get_memory_client, get_memory_id

load_dotenv()

DEFAULT_ACTOR = "demo-user"
SEED_MSG_USER = "저는 건성 피부예요. 민감한 편이라 자극 적은 보습 제품을 선호해요."
SEED_MSG_AGENT = "건성이면서 민감한 피부라는 점 기억해 두겠습니다."
DEFAULT_QUESTION = "보습크림 하나 추천해줘"


def _parse(raw: str) -> str:
    try:
        obj = json.loads(raw)
        return obj.get("preference") or obj.get("context") or raw
    except Exception:
        return raw


def fetch_profile(user_id: str) -> list[str]:
    client = get_memory_client()
    mem_id = get_memory_id()
    lines = []
    # namespace 는 "정확히 일치" 조회이고, prefix 조회는 namespace_path 를 씁니다
    # (공식 문서 RetrieveMemoryRecords 참고). summaries 는 namespace 에
    # {sessionId} 가 포함돼 세션마다 달라지므로, 세션을 모르는 이 함수에서는
    # namespace_path 로 /summaries/{actorId}/ 아래를 전부 훑습니다.
    for ns, q, use_path in [
        (f"/preferences/{user_id}/", "피부타입 선호", False),
        (f"/summaries/{user_id}/",   "이전 대화 요약", True),
    ]:
        try:
            kwargs = {"namespace_path": ns} if use_path else {"namespace": ns}
            for p in client.retrieve_memories(memory_id=mem_id, query=q, **kwargs):
                lines.append(_parse(p["content"]["text"]))
        except Exception:
            pass
    return lines


def seed(user_id: str = DEFAULT_ACTOR) -> None:
    client = get_memory_client()
    mem_id = get_memory_id()
    session_id = f"seed-{uuid.uuid4().hex[:8]}"
    print(f"[seed] user={user_id} session={session_id}")
    client.create_event(
        memory_id=mem_id,
        actor_id=user_id,
        session_id=session_id,
        messages=[(SEED_MSG_USER, "USER"), (SEED_MSG_AGENT, "ASSISTANT")],
    )
    print("[seed] 이벤트 저장 완료. 장기 프로필 추출까지 약 60초 대기 후 ask 실행하세요.")


def ask(question: str, user_id: str = DEFAULT_ACTOR) -> None:
    agent = create_qa_agent()
    profile = fetch_profile(user_id)
    print(f"[프로필] user={user_id}")
    if profile:
        for p in profile:
            print(f"  - {p}")
    else:
        print("  (아직 저장된 프로필 없음)")
    print()

    prompt = question
    if profile:
        prompt = "[사용자 프로필]\n" + "\n".join(profile) + f"\n\n[질문]\n{question}"

    print(f"[질문]\n{question}\n")
    response = str(agent(prompt))
    print(f"[답변]\n{response}\n")

    # 현재 턴도 메모리에 저장
    session_id = f"lab2-{uuid.uuid4().hex[:8]}"
    get_memory_client().create_event(
        memory_id=get_memory_id(),
        actor_id=user_id,
        session_id=session_id,
        messages=[(question, "USER"), (response, "ASSISTANT")],
    )


def chat_loop(user_id: str = DEFAULT_ACTOR) -> None:
    agent = create_qa_agent()
    session_id = f"lab2-{uuid.uuid4().hex[:8]}"
    profile = fetch_profile(user_id)
    print(f"뷰티 Q&A 챗봇 (Lab 2) · user={user_id} · session={session_id}")
    if profile:
        print("[프로필]")
        for p in profile:
            print(f"  - {p}")
    print("종료: Ctrl+C")
    print()

    while True:
        try:
            user_input = input("고객: ").strip()
            if not user_input:
                continue
            prompt = user_input
            if profile:
                prompt = "[프로필]\n" + "\n".join(profile) + f"\n\n[질문]\n{user_input}"
            response = str(agent(prompt))
            print(f"챗봇: {response}\n")
            get_memory_client().create_event(
                memory_id=get_memory_id(),
                actor_id=user_id,
                session_id=session_id,
                messages=[(user_input, "USER"), (response, "ASSISTANT")],
            )
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break


def main() -> None:
    if len(sys.argv) == 1:
        # 기본: profile이 있으면 ask, 없으면 시드하라는 안내
        profile = fetch_profile(DEFAULT_ACTOR)
        if profile:
            ask(DEFAULT_QUESTION)
        else:
            print("저장된 프로필이 없습니다. 먼저 프로필을 시드하세요:")
            print()
            print("  python run_lab2.py seed")
            print()
            print("약 60초 후 다시 실행:")
            print(f"  python run_lab2.py  # 기본 질문 \"{DEFAULT_QUESTION}\"")
        return

    cmd = sys.argv[1]
    if cmd == "seed":
        seed(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ACTOR)
    elif cmd == "ask":
        if len(sys.argv) < 3:
            print("usage: python run_lab2.py ask \"질문 내용\"")
            sys.exit(1)
        ask(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else DEFAULT_ACTOR)
    elif cmd == "--chat":
        chat_loop(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ACTOR)
    else:
        ask(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()
