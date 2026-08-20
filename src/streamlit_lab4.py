"""Lab 4 Streamlit 데모 — 통합 챗봇 (Orchestrator + Memory)."""
import json

import streamlit as st

from agents.orchestrator import create_orchestrator
from memory import get_memory_client, get_memory_id
from ui.chat import (
    extract_tool_trace,
    render_chat,
    render_header,
    reset_session,
)

st.set_page_config(page_title="Lab 4 — 통합 데모", page_icon="✨", layout="centered")

render_header(
    title="뷰티 AI 상담사 — 통합 데모",
    subtitle="맥락 기반 Q&A · 상품 추천 · 정보 요약을 한 에이전트가 모두 수행",
    lab_tag="LAB 4",
)

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = create_orchestrator()
if "lab4_user_id" not in st.session_state:
    st.session_state.lab4_user_id = "thewhoo-user-001"


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
    except Exception:
        return []


with st.sidebar:
    st.subheader("이 데모에서 확인할 것")
    st.markdown(
        "**고객 요구사항 3종**\n"
        "- ① **맥락 기반 대화형 Q&A** — 메모리 + KB\n"
        "- ② **상품 검색 · 추천** — Gateway 도구 연동\n"
        "- ③ **주요 정보 요약** — 응답을 깔끔하게 정리"
    )

    st.divider()
    user_id = st.text_input(
        "user_id", value=st.session_state.lab4_user_id, key="lab4_uid"
    )
    if user_id != st.session_state.lab4_user_id:
        st.session_state.lab4_user_id = user_id
        reset_session("lab4")
        st.rerun()

    st.subheader("저장된 선호")
    prefs = _fetch_prefs(st.session_state.lab4_user_id)
    if prefs:
        for p in prefs:
            st.markdown(f"- {p}")
    else:
        st.caption("_(아직 없음 — 피부타입을 말해보세요)_")

    st.divider()
    if st.button("새 세션"):
        reset_session("lab4")
        st.rerun()


SCENARIOS = [
    ("① 프로필 저장", "저는 건성이고 민감한 편이에요. 자극 적은 제품을 선호해요."),
    ("② 맥락 추천", "보습 세럼 하나 추천해줘. 재고도 알려줘"),
    ("③ 복합 요약", "천기단 화현 크림 성분·사용법·프로모션 정리해줘"),
]


def handler(user_msg: str, session_id: str) -> tuple[str, dict]:
    user_id = st.session_state.lab4_user_id
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

    profile_str = "\n".join(lines) if lines else "(없음)"
    prompt = f"[사용자 프로필]\n{profile_str}\n\n[질문]\n{user_msg}"

    result = st.session_state.orchestrator(prompt)
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
    state_key="lab4",
    placeholder="뷰티에 관한 무엇이든 물어보세요...",
    scenarios=SCENARIOS,
    show_trace=True,
)
