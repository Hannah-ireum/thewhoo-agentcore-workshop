"""Lab 1 Streamlit 데모 — KB 기반 상품 Q&A."""
import streamlit as st

from agents.qa_agent import create_qa_agent
from ui.chat import render_header, render_chat, extract_tool_trace

st.set_page_config(page_title="Lab 1 — 상품 Q&A", page_icon="🔍", layout="centered")

render_header(
    title="상품 정보 Q&A",
    subtitle="Knowledge Base에서 근거를 찾아 답변하는 Strands Agent",
    lab_tag="LAB 1",
)

if "qa_agent" not in st.session_state:
    st.session_state.qa_agent = create_qa_agent()

with st.sidebar:
    st.subheader("이 Lab의 포인트")
    st.markdown(
        "- `kb_retrieve` 도구로 Bedrock Knowledge Base 검색\n"
        "- 근거 기반 답변 (지어내지 않음)\n"
        "- 재고/프로모션 같은 실시간 정보는 **모른다고** 답함 (Lab 3에서 연결)"
    )
    if st.button("대화 초기화"):
        from ui.chat import reset_session

        reset_session("lab1")
        st.rerun()

SCENARIOS = [
    ("성분 질문", "천기단 화현 크림 주요 성분 알려주세요"),
    ("사용법 질문", "천기단 화현 아이크림 사용할 때 주의사항 뭐야?"),
    ("한계 확인", "WHOO-00101 지금 재고 있어?"),
]


def handler(user_msg: str, session_id: str) -> tuple[str, dict]:
    result = st.session_state.qa_agent(user_msg)
    return str(result), {"trace": extract_tool_trace(result)}


render_chat(
    handler=handler,
    state_key="lab1",
    placeholder="상품 정보에 대해 물어보세요...",
    scenarios=SCENARIOS,
    show_trace=True,
)
