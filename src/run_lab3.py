"""Lab 3 실행 파일 — Recommend Agent + AgentCore Gateway (MCP).

사용법 (src/ 디렉토리에서):
  python run_lab3.py                        # 기본 4가지 시나리오 모두 실행 (도구 호출 내역 표시)
  python run_lab3.py "질문"                 # 질문 1개만 실행
  python run_lab3.py --chat                 # 대화형 REPL
  python run_lab3.py --quiet ...            # 도구 호출 출력 끄기

환경변수:
  AGENTCORE_GATEWAY_URL, AWS_REGION
"""
from __future__ import annotations

import sys

from dotenv import load_dotenv

from agents.recommend_agent import ask_recommend_agent, chat_session

load_dotenv()

SCENARIOS = [
    ("키워드 검색", "5만원 이하 향수 뭐 있어?"),
    ("개인화 추천", "건성 피부에 좋은 보습 세럼 추천해줘"),
    ("재고 조회", "WHOO-00101 재고 있어?"),
    ("복합 질의", "민감성에 진정 좋은 거 추천하고, 프로모션 있는지도 알려줘"),
]


def ask_once(question: str, verbose: bool = True) -> None:
    print(f"[질문]\n{question}\n")
    if verbose:
        print("[도구 호출 내역]")
    response = ask_recommend_agent(question, verbose=verbose)
    print(f"\n[답변]\n{response}\n")


def run_scenarios(verbose: bool = True) -> None:
    for i, (label, q) in enumerate(SCENARIOS, 1):
        print("=" * 60)
        print(f"[시나리오 {i}] {label}")
        print("=" * 60)
        ask_once(q, verbose=verbose)


def chat_loop(verbose: bool = True) -> None:
    """대화 이력이 같은 세션 동안 유지됩니다. (프로세스 종료 시 사라짐)"""
    print("뷰티 추천 챗봇 (Lab 3) — 종료: Ctrl+C")
    print("같은 세션 안에서는 이전 턴을 기억합니다. (Memory 영속은 Lab 4)")
    print()
    with chat_session(verbose=verbose) as chat:
        while True:
            try:
                user_input = input("고객: ").strip()
                if not user_input:
                    continue
                response = chat(user_input)
                print(f"\n챗봇: {response}\n")
            except KeyboardInterrupt:
                print("\n종료합니다.")
                break


def main() -> None:
    args = sys.argv[1:]
    verbose = True
    if args and args[0] == "--quiet":
        verbose = False
        args = args[1:]

    if not args:
        run_scenarios(verbose=verbose)
        return
    if args[0] == "--chat":
        chat_loop(verbose=verbose)
        return
    ask_once(" ".join(args), verbose=verbose)


if __name__ == "__main__":
    main()
