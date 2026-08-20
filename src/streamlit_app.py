"""Streamlit UI — 뷰티 AI 챗봇."""
import uuid
import streamlit as st
from dotenv import load_dotenv
from agents.orchestrator import create_orchestrator
from memory import retrieve_session_context, save_turn

load_dotenv()

st.set_page_config(page_title="뷰티 AI 챗봇", page_icon="✨", layout="centered")
st.title("✨ 뷰티 AI 챗봇")
st.caption("상품 정보, 피부 타입별 추천, 재고 확인까지 한번에")

# 세션 상태 초기화
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = create_orchestrator()

ACTOR_ID = "streamlit-user"

# 이전 메시지 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 입력 처리
if prompt := st.chat_input("궁금한 점을 물어보세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("답변을 준비하고 있어요..."):
            context = retrieve_session_context(ACTOR_ID, st.session_state.session_id)
            full_prompt = prompt
            if context:
                full_prompt = f"[이전 대화 맥락]\n{context}\n\n[현재 요청]\n{prompt}"

            response = st.session_state.orchestrator(full_prompt)
            response_str = str(response)

            save_turn(ACTOR_ID, st.session_state.session_id, prompt, response_str)

        st.write(response_str)
        st.session_state.messages.append({"role": "assistant", "content": response_str})
