"""Lab 4 실행 파일 — Orchestrator + Agents-as-Tools + Memory.

사용법 (src/ 디렉토리에서):
  python run_lab4.py                        # 3가지 시나리오 순차 실행
  python run_lab4.py "질문"                 # 1개 질문만 실행
  python run_lab4.py --chat [user_id]       # 대화형 REPL

환경변수:
  KB_ID, AWS_REGION, AGENTCORE_MEMORY_ID, AGENTCORE_GATEWAY_URL
"""
from __future__ import annotations

import sys
import uuid

from dotenv import load_dotenv

from agents.orchestrator import create_orchestrator
from memory import retrieve_session_context, save_turn

load_dotenv()

DEFAULT_ACTOR = "demo-user"
SCENARIOS = [
    ("① 맥락 기반 Q&A", "천기단 화현 크림 주요 성분 알려줘"),
    ("② 상품 추천", "건성 피부에 맞는 보습 세럼 추천해줘. 재고도 확인해줘"),
    ("③ 요약 + 프로모션", "지금 스킨케어 프로모션 있으면 깔끔하게 정리해줘"),
]


def _invoke(orch, user_id: str, session_id: str, user_input: str) -> str:
    context = retrieve_session_context(user_id, session_id)
    prompt = user_input
    if context:
        prompt = f"[이전 대화 맥락]\n{context}\n\n[현재 요청]\n{user_input}"
    response = str(orch(prompt))
    save_turn(user_id, session_id, user_input, response)
    return response


def run_scenarios(user_id: str = DEFAULT_ACTOR) -> None:
    orch = create_orchestrator()
    session_id = str(uuid.uuid4())
    print(f"user={user_id}  session={session_id}\n")

    for label, q in SCENARIOS:
        print("=" * 60)
        print(label)
        print("=" * 60)
        print(f"[질문]\n{q}\n")
        response = _invoke(orch, user_id, session_id, q)
        print(f"[답변]\n{response}\n")


def ask_once(question: str, user_id: str = DEFAULT_ACTOR) -> None:
    orch = create_orchestrator()
    session_id = str(uuid.uuid4())
    print(f"[질문]\n{question}\n")
    response = _invoke(orch, user_id, session_id, question)
    print(f"[답변]\n{response}\n")


def chat_loop(user_id: str = DEFAULT_ACTOR) -> None:
    orch = create_orchestrator()
    session_id = str(uuid.uuid4())
    print(f"뷰티 AI 챗봇 (Lab 4) · user={user_id} · session={session_id}")
    print("종료: Ctrl+C\n")

    while True:
        try:
            user_input = input("고객: ").strip()
            if not user_input:
                continue
            response = _invoke(orch, user_id, session_id, user_input)
            print(f"챗봇: {response}\n")
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break


def main() -> None:
    if len(sys.argv) == 1:
        run_scenarios()
        return
    if sys.argv[1] == "--chat":
        chat_loop(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ACTOR)
        return
    ask_once(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()
