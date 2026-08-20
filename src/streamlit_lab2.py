"""Lab 2 Streamlit 데모 — 메모리 붙은 Q&A 챗봇."""
import json
import os

import streamlit as st

from agents.qa_agent import create_qa_agent
from memory import get_memory_client, get_memory_id
from ui.chat import (
    extract_tool_trace,
    render_chat,
    render_header,
    reset_session,
)

st.set_page_config(page_title="Lab 2 — 메모리 챗봇", page_icon="🧠", layout="centered")

render_header(
    title="맥락을 기억하는 챗봇",
    subtitle="AgentCore Memory 3-strategy로 사용자 선호·이전 대화 맥락 유지",
    lab_tag="LAB 2",
)

if "qa_agent" not in st.session_state:
    st.session_state.qa_agent = create_qa_agent()
if "lab2_user_id" not in st.session_state:
    st.session_state.lab2_user_id = "thewhoo-user-001"


def _parse(raw: str) -> str:
    try:
        obj = json.loads(raw)
        return obj.get("preference") or obj.get("context") or raw
    except Exception:
        return raw


def _fetch_prefs(user_id: str) -> list[str]:
    try:
        client = get_memory_client()
        prefs = client.retrieve_memories(
            memory_id=get_memory_id(),
            namespace=f"/preferences/{user_id}/",
            query="피부타입 선호",
        )
        return [_parse(p["content"]["text"]) for p in prefs]
    except Exception as e:
        return [f"(메모리 조회 실패: {e})"]


with st.sidebar:
    st.subheader("현재 사용자")
    user_id = st.text_input(
        "user_id", value=st.session_state.lab2_user_id, key="lab2_uid_input"
    )
    if user_id != st.session_state.lab2_user_id:
        st.session_state.lab2_user_id = user_id
        reset_session("lab2")
        st.rerun()

    st.divider()
    st.subheader("장기 메모리 — 선호")
    st.caption("USER_PREFERENCE strategy가 추출한 사용자 선호")
    prefs = _fetch_prefs(st.session_state.lab2_user_id)
    if prefs:
        for p in prefs:
            st.markdown(f"- {p}")
    else:
        st.markdown("_(아직 저장된 선호 없음 — 피부타입을 말해보세요)_")

    st.divider()
    if st.button("새 세션 시작"):
        reset_session("lab2")
        st.rerun()
    st.caption(
        "**팁**: 이 Lab에서 '저는 지성 피부예요'라고 한 뒤 60초 정도 기다리면 "
        "왼쪽 선호 목록에 추가됩니다. 새 세션을 시작해도 그 정보가 유지됩니다."
    )


SCENARIOS = [
    ("프로필 저장", "저는 지성 피부예요. 모공이 넓은 게 고민이에요."),
    ("맥락 없이", "보습크림 추천해주세요"),
    ("이어지는 질문", "그 중에서 재고 있는 거로 알려줘"),
]


def handler(user_msg: str, session_id: str) -> tuple[str, dict]:
    user_id = st.session_state.lab2_user_id
    client = get_memory_client()
    memory_id = get_memory_id()

    lines = []
    for ns, query in [
        (f"/preferences/{user_id}/", "피부타입 선호"),
        (f"/summaries/{user_id}/{session_id}/", "이전 대화 요약"),
    ]:
        try:
            for p in client.retrieve_memories(
                memory_id=memory_id, namespace=ns, query=query
            ):
                lines.append(f"- {_parse(p['content']['text'])}")
        except Exception:
            pass

    prompt = user_msg
    if lines:
        prompt = (
            f"[사용자 프로필]\n" + "\n".join(lines) + f"\n\n[질문]\n{user_msg}"
        )

    result = st.session_state.qa_agent(prompt)
    response = str(result)

    try:
        client.create_event(
            memory_id=memory_id,
            actor_id=user_id,
            session_id=session_id,
            messages=[(user_msg, "USER"), (response, "ASSISTANT")],
        )
    except Exception as e:
        response += f"\n\n_(메모리 저장 실패: {e})_"

    return response, {
        "trace": {
            "injected_profile": lines,
            "tools": extract_tool_trace(result),
        }
    }


render_chat(
    handler=handler,
    state_key="lab2",
    placeholder="피부 고민을 말해보거나 추천을 요청해보세요...",
    scenarios=SCENARIOS,
    show_trace=True,
)
