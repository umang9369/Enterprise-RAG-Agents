import base64
import os
import time
import uuid

import logfire
import requests
import streamlit as st
from dotenv import load_dotenv

# Load environment variables explicitly from the root directory
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=env_path)

# ── Logfire ──────────────────────────────────────────────────────────────────
LOGFIRE_STATUS = "Unknown"
try:
    token = os.getenv("LOGFIRE_TOKEN")
    base_url = os.getenv("LOGFIRE_BASE_URL")
    if not base_url and token and token.startswith("pylf_v2_eu_"):
        base_url = "https://logfire-eu.pydantic.dev"
    if not token:
        LOGFIRE_STATUS = "Standby"
    else:
        logfire.configure(
            token=token,
            advanced=logfire.AdvancedOptions(base_url=base_url) if base_url else None,
        )
        LOGFIRE_STATUS = "Connected"
except Exception:
    LOGFIRE_STATUS = "Error"

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enterprise Agentic RAG",
    page_icon="🤖",
    layout="wide",
)

# ── LOAD BACKGROUND IMAGE ─────────────────────────────────────────────────────
_bg_path = os.path.join(os.path.dirname(__file__), "assets", "bg.jpg")
_bg_b64 = ""
if os.path.exists(_bg_path):
    with open(_bg_path, "rb") as f:
        _bg_b64 = base64.b64encode(f.read()).decode()

# ── AVATARS ───────────────────────────────────────────────────────────────────
AI_AVATAR = "🤖"
USER_AVATAR = "👤"

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "groq_api_key" not in st.session_state:
    st.session_state.groq_api_key = ""
if "key_panel_open" not in st.session_state:
    st.session_state.key_panel_open = False

# ── CSS STYLING & BACKGROUND ──────────────────────────────────────────────────
bg_css = f"background-image: url('data:image/jpeg;base64,{_bg_b64}');" if _bg_b64 else ""

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
* {{ font-family: 'Inter', sans-serif; }}

/* ── Background image on main chat area (25% opacity) ── */
[data-testid="stMain"]::before {{
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    {bg_css}
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    opacity: 0.25;
    z-index: 0;
    pointer-events: none;
}}

/* ── App dark theme overlay ── */
[data-testid="stAppViewContainer"] {{
    background: rgba(8, 8, 12, 0.88);
}}
[data-testid="stMain"] {{
    background: transparent !important;
}}
[data-testid="stHeader"] {{
    background: rgba(8, 8, 12, 0.85) !important;
    backdrop-filter: blur(10px);
}}
[data-testid="stSidebar"] {{
    background: rgba(10, 10, 18, 0.98) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
}}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {{
    background: rgba(20, 20, 32, 0.78) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 14px !important;
    backdrop-filter: blur(12px);
    margin-bottom: 12px;
}}

/* ── Chat input ── */
[data-testid="stChatInput"] textarea {{
    background: rgba(18, 18, 28, 0.92) !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 12px !important;
    color: #e8e8f0 !important;
}}
[data-testid="stChatInput"] textarea:focus {{
    border-color: rgba(139, 92, 246, 0.6) !important;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
}}

/* ── Centered Pill API Key Button ── */
div.st-key-center_api_key_btn button {{
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255, 255, 255, 0.25) !important;
    border-radius: 50px !important;
    padding: 10px 24px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
    box-shadow: 0 4px 18px rgba(99, 102, 241, 0.45) !important;
    transition: all 0.25s ease !important;
}}
div.st-key-center_api_key_btn button:hover {{
    background: linear-gradient(135deg, #818cf8, #a78bfa) !important;
    box-shadow: 0 6px 26px rgba(99, 102, 241, 0.65) !important;
    transform: translateY(-2px) !important;
}}

/* ── Sliding Slider/Drawer Card Animation ── */
@keyframes slideDownDrawer {{
    0% {{
        opacity: 0;
        transform: translateY(-20px) scale(0.98);
    }}
    100% {{
        opacity: 1;
        transform: translateY(0) scale(1);
    }}
}}

div.st-key-api_drawer_box {{
    animation: slideDownDrawer 0.32s cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
    margin: 10px 0 26px 0 !important;
}}

div.st-key-api_drawer_box > div {{
    background: rgba(13, 13, 26, 0.96) !important;
    border: 1px solid rgba(99, 102, 241, 0.4) !important;
    border-radius: 16px !important;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7), 0 0 24px rgba(99, 102, 241, 0.18) !important;
    backdrop-filter: blur(24px) !important;
    padding: 24px !important;
}}

/* ── Input field inside drawer ── */
div.st-key-drawer_key_input_field input {{
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(99, 102, 241, 0.35) !important;
    border-radius: 10px !important;
    color: #e8e8f8 !important;
    font-family: 'JetBrains Mono', monospace !important;
    padding: 12px 14px !important;
}}
div.st-key-drawer_key_input_field input:focus {{
    border-color: rgba(139, 92, 246, 0.8) !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2) !important;
}}

/* ── Standard buttons ── */
.stButton > button {{
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}}
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 16px 0;">
        <h1 style="font-size:22px;font-weight:700;color:#e8e8f8;margin:0;">🧠 Agent OS</h1>
        <p style="font-size:12px;color:#6b7280;margin:4px 0 0 0;">Enterprise RAG · Powered by Groq</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # ── Key Status in Sidebar ──
    if st.session_state.groq_api_key:
        masked = st.session_state.groq_api_key[:8] + "••••••••"
        st.markdown(f"""
        <div style="
            background: rgba(16,185,129,0.08);
            border: 1px solid rgba(16,185,129,0.25);
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 12px;
            color: #6ee7b7;
            font-family: monospace;
        ">🟢 Groq Key active: {masked}</div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="
            background: rgba(245,158,11,0.08);
            border: 1px solid rgba(245,158,11,0.25);
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 12px;
            color: #fcd34d;
        ">🔴 No key set — click the center button above</div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

    # Sidebar toggle button
    s_label = "▲ Close API Keys" if st.session_state.key_panel_open else "🔑 Manage API Key"
    if st.button(s_label, key="sidebar_key_btn", use_container_width=True):
        st.session_state.key_panel_open = not st.session_state.key_panel_open
        st.rerun()

    st.divider()

    # ── System Status ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="display:flex;flex-direction:column;gap:8px;">
        <div style="
            background:rgba(99,102,241,0.08);
            border:1px solid rgba(99,102,241,0.2);
            border-radius:8px;padding:10px 14px;
        ">
            <div style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;
                        letter-spacing:0.5px;margin-bottom:4px;">Logfire</div>
            <div style="font-size:13px;color:#a5b4fc;">{'✅ ' if 'Connected' in LOGFIRE_STATUS else '⏸ '}{LOGFIRE_STATUS}</div>
        </div>
        <div style="
            background:rgba(99,102,241,0.08);
            border:1px solid rgba(99,102,241,0.2);
            border-radius:8px;padding:10px 14px;
        ">
            <div style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;
                        letter-spacing:0.5px;margin-bottom:4px;">Memory ID</div>
            <div style="font-size:12px;color:#a5b4fc;font-family:monospace;">
                {st.session_state.session_id[:12]}…
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

    if st.button("🗑️ Clear History & Memory", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()


# ── CENTERED API KEY BUTTON ───────────────────────────────────────────────────
col_l, col_center, col_r = st.columns([1, 1.4, 1])
with col_center:
    is_open = st.session_state.key_panel_open
    has_key = bool(st.session_state.groq_api_key)

    if is_open:
        pill_label = "▲ Close API Keys"
    elif has_key:
        masked_disp = st.session_state.groq_api_key[:8] + "••••"
        pill_label = f"🔑 API Keys · 🟢 Active ({masked_disp})"
    else:
        pill_label = "🔑 API Keys · 🔴 Key Required"

    if st.button(pill_label, key="center_api_key_btn", use_container_width=True):
        st.session_state.key_panel_open = not is_open
        st.rerun()

# ── SLIDING DRAWER / SLIDER COMPONENT ─────────────────────────────────────────
if st.session_state.key_panel_open:
    sc1, sc_drawer, sc2 = st.columns([0.4, 3.2, 0.4])
    with sc_drawer:
        with st.container(key="api_drawer_box", border=True):
            # Header
            st.markdown("""
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 14px;">
                <div>
                    <div style="font-size:18px; font-weight:700; color:#f3f4f6; display:flex; align-items:center; gap:8px;">
                        🔑 Groq API Key Configuration
                    </div>
                    <div style="font-size:12px; color:#9ca3af; margin-top:3px;">
                        Session-only · Never stored permanently · Billed to your Groq account
                    </div>
                </div>
                <a href="https://console.groq.com/keys" target="_blank"
                   style="font-size:12px; color:#a5b4fc; background:rgba(99,102,241,0.15); border:1px solid rgba(99,102,241,0.3); padding:5px 12px; border-radius:6px; text-decoration:none; white-space:nowrap; font-weight:600;">
                    Get Free Key ↗
                </a>
            </div>
            """, unsafe_allow_html=True)

            if has_key:
                st.markdown(f"""
                <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.25); border-radius:8px; padding:10px 14px; margin-bottom:12px; font-size:13px; color:#6ee7b7; font-family:monospace;">
                    🟢 Current Key: <b>{st.session_state.groq_api_key[:8]}••••••••••••</b>
                </div>
                """, unsafe_allow_html=True)

            key_input = st.text_input(
                "Groq API Key",
                value=st.session_state.groq_api_key if has_key else "",
                placeholder="Paste your gsk_... key here",
                type="password",
                label_visibility="collapsed",
                key="drawer_key_input_field",
            )

            # Action buttons inside drawer
            act_col1, act_col2, act_col3 = st.columns([1.6, 1, 1])
            with act_col1:
                if st.button("💾 Apply Key", key="btn_apply_key", type="primary", use_container_width=True):
                    cleaned = key_input.strip()
                    if cleaned:
                        st.session_state.groq_api_key = cleaned
                        st.session_state.key_panel_open = False
                        st.toast("✅ Groq API Key saved and activated!", icon="🚀")
                        st.rerun()
                    else:
                        st.warning("Please paste a valid Groq API key (starts with gsk_).")
            with act_col2:
                if has_key and st.button("🗑️ Remove", key="btn_remove_key", use_container_width=True):
                    st.session_state.groq_api_key = ""
                    st.session_state.key_panel_open = False
                    st.toast("Key removed.", icon="ℹ️")
                    st.rerun()
            with act_col3:
                if st.button("✕ Close", key="btn_close_drawer", use_container_width=True):
                    st.session_state.key_panel_open = False
                    st.rerun()


# ── MAIN CHAT AREA ────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding: 10px 0 20px 0;">
    <h1 style="font-size:28px;font-weight:700;color:#e8e8f8;margin:0;">🤖 Enterprise Agentic Assistant</h1>
    <p style="font-size:13px;color:#6b7280;margin:4px 0 0 0;">
        Kubernetes · Intel Hardware · Enterprise Networking
    </p>
</div>
""", unsafe_allow_html=True)

# Display history
for message in st.session_state.messages:
    avatar = AI_AVATAR if message["role"] == "assistant" else USER_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# Gate: block until key is provided
if not st.session_state.groq_api_key:
    st.markdown("""
    <div style="
        background: rgba(99,102,241,0.06);
        border: 1px solid rgba(99,102,241,0.2);
        border-radius: 12px;
        padding: 28px 32px;
        text-align: center;
        margin-top: 24px;
    ">
        <div style="font-size:40px;margin-bottom:12px;">🔑</div>
        <div style="font-size:18px;font-weight:600;color:#e8e8f8;margin-bottom:8px;">
            Groq API Key Required
        </div>
        <div style="font-size:14px;color:#9ca3af;line-height:1.7;max-width:480px;margin:0 auto 16px auto;">
            Click the <b style="color:#a5b4fc;">🔑 API Keys</b> button in the center above to enter your Groq key and start chatting.<br>
            Don't have a key? Get a free one at
            <a href="https://console.groq.com/keys" target="_blank"
               style="color:#a5b4fc;text-decoration:none;font-weight:600;">console.groq.com/keys ↗</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    gc1, gc2, gc3 = st.columns([1, 1.2, 1])
    with gc2:
        if not st.session_state.key_panel_open:
            if st.button("🔑 Enter Groq Key Now", key="gate_open_key_btn", type="primary", use_container_width=True):
                st.session_state.key_panel_open = True
                st.rerun()

    st.stop()

# Chat Input
if prompt := st.chat_input("Ask about Kubernetes, Intel hardware, or enterprise networking..."):
    with logfire.span("💬 Chat", session_id=st.session_state.session_id):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar=AI_AVATAR):
            with st.status("🔍 Agent is thinking...", expanded=True) as status:
                try:
                    base_url = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
                    url = f"{base_url}/query"
                    payload = {"q": prompt, "thread_id": st.session_state.session_id}
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {os.getenv('RAG_API_KEY', '')}",
                        "X-User-Groq-Key": st.session_state.groq_api_key,
                    }
                    response = requests.post(url, json=payload, headers=headers, timeout=180)

                    if response.status_code == 401:
                        detail = response.json().get("detail", "Unauthorized")
                        raise RuntimeError(f"🔑 {detail}")

                    response.raise_for_status()
                    data = response.json()

                    if data.get("status") == "Blocked by guardrails.":
                        status.update(label="🛡️ Blocked by guardrails", state="complete", expanded=False)
                        full_answer = data.get("answer", "Blocked by guardrails.")
                    elif "answer" in data:
                        status.update(label="✅ Answer Synthesized", state="complete", expanded=False)
                        full_answer = data.get("answer", "No response.")
                    else:
                        raise RuntimeError(f"Unexpected response: {data}")

                    for step in data.get("thought_process", []):
                        st.write(f"⚙️ {step}")

                    sources = data.get("sources", [])
                    if sources:
                        with st.expander("📄 View Retrieved Context"):
                            for i, source in enumerate(sources):
                                preview = source[:100].replace("\n", " ") + "..."
                                with st.expander(f"Chunk {i + 1}: {preview}"):
                                    st.info(source)

                except Exception as e:
                    logfire.error(f"❌ Error: {e}")
                    status.update(label="❌ Failed", state="error")
                    st.error(f"Error: {e}")
                    st.stop()

            # Typewriter streaming
            answer_placeholder = st.empty()
            curr_text = ""
            for char in full_answer:
                curr_text += char
                answer_placeholder.markdown(curr_text + "▌")
                time.sleep(0.005)
            answer_placeholder.markdown(full_answer)

            st.session_state.messages.append({"role": "assistant", "content": full_answer})