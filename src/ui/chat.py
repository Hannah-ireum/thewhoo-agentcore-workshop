"""Streamlit 공용 챗 컴포넌트 — Lab 1~5에서 재사용."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import streamlit as st


def init_session(
    state_key: str = "default",
    reset_on_switch: bool = False,
) -> tuple[str, list[dict]]:
    """세션 ID + 메시지 버퍼를 초기화해서 반환."""
    sid_key = f"{state_key}_session_id"
    msg_key = f"{state_key}_messages"

    if sid_key not in st.session_state:
        st.session_state[sid_key] = str(uuid.uuid4())
    if msg_key not in st.session_state:
        st.session_state[msg_key] = []

    return sid_key, msg_key


def render_header(title: str, subtitle: str, lab_tag: str) -> None:
    """상단 배너."""
    st.markdown(
        f"""
        <div style="background: linear-gradient(90deg, #f5f0ff 0%, #fff0f5 100%);
                    padding: 16px 20px; border-radius: 12px; margin-bottom: 20px;">
            <div style="color: #7c3aed; font-size: 12px; font-weight: 600; letter-spacing: 0.5px;">
                {lab_tag}
            </div>
            <div style="font-size: 22px; font-weight: 700; margin-top: 4px;">{title}</div>
            <div style="color: #6b7280; font-size: 14px; margin-top: 4px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_scenario_buttons(
    scenarios: list[tuple[str, str]],
    columns: int = 3,
) -> str | None:
    """추천 질문 버튼. 클릭된 질문 텍스트 반환."""
    clicked: str | None = None
    cols = st.columns(columns)
    for i, (label, prompt) in enumerate(scenarios):
        with cols[i % columns]:
            if st.button(label, key=f"scenario_{i}", use_container_width=True):
                clicked = prompt
    return clicked


def render_chat(
    handler: Callable[[str, str], tuple[str, dict[str, Any]]],
    state_key: str = "default",
    placeholder: str = "궁금한 점을 입력하세요...",
    scenarios: list[tuple[str, str]] | None = None,
    show_trace: bool = False,
) -> None:
    """챗 인터페이스.

    handler(user_msg, session_id) → (response, meta)
      meta 는 사이드바/트레이스에 쓸 부가 정보 (dict).
    """
    sid_key, msg_key = init_session(state_key)

    for msg in st.session_state[msg_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if show_trace and msg.get("trace"):
                with st.expander("도구 호출 내역"):
                    st.json(msg["trace"])

    prompt = None
    if scenarios:
        st.caption("아래 질문을 눌러보거나 직접 입력하세요")
        clicked = render_scenario_buttons(scenarios)
        if clicked:
            prompt = clicked

    user_input = st.chat_input(placeholder)
    if user_input:
        prompt = user_input

    if prompt:
        st.session_state[msg_key].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("답변을 준비하고 있어요..."):
                response, meta = handler(prompt, st.session_state[sid_key])
            st.markdown(response)
            if show_trace and meta.get("trace"):
                with st.expander("도구 호출 내역"):
                    st.json(meta["trace"])

        st.session_state[msg_key].append(
            {"role": "assistant", "content": response, "trace": meta.get("trace")}
        )


def reset_session(state_key: str = "default") -> None:
    """세션 초기화 (ID 재발급 + 메시지 비우기)."""
    sid_key = f"{state_key}_session_id"
    msg_key = f"{state_key}_messages"
    st.session_state[sid_key] = str(uuid.uuid4())
    st.session_state[msg_key] = []


def extract_tool_trace(agent_result: Any) -> list[dict]:
    """Strands AgentResult에서 도구 호출 내역 추출."""
    trace = []
    try:
        metrics = getattr(agent_result, "metrics", None)
        if metrics and hasattr(metrics, "tool_metrics"):
            for name, tm in metrics.tool_metrics.items():
                trace.append(
                    {
                        "tool": name,
                        "call_count": tm.call_count,
                        "total_time": round(tm.total_time, 2),
                    }
                )
    except Exception:
        pass
    return trace
