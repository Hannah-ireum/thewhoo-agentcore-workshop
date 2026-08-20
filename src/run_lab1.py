"""Lab 1 실행 파일 — Q&A Agent + Knowledge Base RAG.

사용법:
  python run_lab1.py                    # 기본 예제 질문 1개 실행
  python run_lab1.py "질문 내용"        # 직접 질문 전달
  python run_lab1.py --chat             # 대화형 REPL

주의: src/ 디렉토리에서 실행하세요.
"""
import sys
from dotenv import load_dotenv
from agents.qa_agent import create_qa_agent

load_dotenv()

DEFAULT_QUESTION = "천기단 화현 크림 주요 성분이랑 사용법 알려주세요"


def ask_once(agent, question: str) -> None:
    print(f"[질문]\n{question}\n")
    response = agent(question)
    print(f"[답변]\n{response}\n")


def chat_loop(agent) -> None:
    print("뷰티 Q&A 챗봇 (Lab 1) — 종료: Ctrl+C")
    print()
    while True:
        try:
            user_input = input("고객: ").strip()
            if not user_input:
                continue
            response = agent(user_input)
            print(f"챗봇: {response}\n")
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break


def main() -> None:
    agent = create_qa_agent()

    if len(sys.argv) == 1:
        ask_once(agent, DEFAULT_QUESTION)
        return

    if sys.argv[1] == "--chat":
        chat_loop(agent)
        return

    ask_once(agent, " ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()
