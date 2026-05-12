"""
Streamlit Dashboard — Web UI for the LLM API Gateway.
Provides API key management, provider configuration, testing, and log viewing.
"""

import streamlit as st
import requests
import json
import time

# ---------- Config ----------

# Point to the FastAPI backend — override via env var or Streamlit secrets
import os
API_BASE = os.getenv("GATEWAY_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="LLM Gateway Dashboard",
    page_icon="🔀",
    layout="wide",
)

# ---------- Helper functions ----------

def api_get(path: str) -> dict:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        st.error("Cannot connect to the Gateway API. Make sure the FastAPI server is running.")
        return {}
    except Exception as e:
        st.error(f"API error: {e}")
        return {}


def api_post(path: str, data: dict) -> dict:
    try:
        r = requests.post(f"{API_BASE}{path}", json=data, timeout=120)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        st.error(f"API error: {detail}")
        return {"error": detail}
    except requests.ConnectionError:
        st.error("Cannot connect to the Gateway API.")
        return {"error": "Connection failed"}
    except Exception as e:
        st.error(f"Error: {e}")
        return {"error": str(e)}


# ---------- Sidebar: API Key Management ----------

st.sidebar.title("🔑 API Key Management")

providers_data = api_get("/providers")
providers = providers_data.get("providers", [])

if providers:
    for p in providers:
        with st.sidebar.expander(f"{'🟢' if p['has_key'] and p['enabled'] else '⚪'} {p['name']} ({p['tier']})"):
            # API key input
            if p["id"] != "ollama":
                key_input = st.text_input(
                    f"API Key",
                    type="password",
                    key=f"key_{p['id']}",
                    placeholder="Enter API key...",
                    help=f"{'✅ Key configured' if p['has_key'] else '❌ No key set'}",
                )
                if st.button("Save Key", key=f"save_{p['id']}"):
                    if key_input:
                        result = api_post("/providers/key", {"provider": p["id"], "api_key": key_input})
                        if "error" not in result:
                            st.success("Key saved!")
                            st.rerun()
                    else:
                        st.warning("Enter a key first")

                if p["has_key"]:
                    if st.button("🗑️ Remove Key", key=f"remove_{p['id']}", type="secondary"):
                        result = api_post("/providers/key/remove", {"provider": p["id"]})
                        if "error" not in result:
                            st.success("Key removed!")
                            st.rerun()
            else:
                st.info("Ollama runs locally — no API key needed")

            # Enable/disable toggle
            enabled = st.checkbox(
                "Enabled",
                value=p["enabled"],
                key=f"toggle_{p['id']}",
            )
            if enabled != p["enabled"]:
                api_post("/providers/toggle", {"provider": p["id"], "enabled": enabled})
                st.rerun()

            # Model selection
            if p["models"]:
                current_idx = p["models"].index(p["selected_model"]) if p["selected_model"] in p["models"] else 0
                selected_model = st.selectbox(
                    "Model",
                    p["models"],
                    index=current_idx,
                    key=f"model_{p['id']}",
                )
                if selected_model != p["selected_model"]:
                    api_post("/providers/model", {"provider": p["id"], "model": selected_model})
                    st.rerun()

st.sidebar.divider()
if st.sidebar.button("🗑️ Clear Cache"):
    api_post("/cache/clear", {})
    st.sidebar.success("Cache cleared!")


# ---------- Main area ----------

st.title("🔀 LLM API Gateway")
st.caption("Unified LLM access with automatic failover — free providers first, paid as fallback")

tab1, tab2, tab3 = st.tabs(["💬 Test API", "📊 Provider Status", "📋 Failover Logs"])

# ---------- Tab 1: Test API ----------

with tab1:
    st.subheader("Send a Prompt")

    col1, col2 = st.columns([3, 1])
    with col1:
        prompt = st.text_area(
            "Prompt",
            placeholder="Enter your prompt here...",
            height=150,
            key="prompt_input",
        )
    with col2:
        max_tokens = st.slider("Max Tokens", 64, 4096, 1024, key="max_tokens")
        temperature = st.slider("Temperature", 0.0, 2.0, 0.7, step=0.1, key="temperature")
        use_cache = st.checkbox("Use Cache", value=True, key="use_cache")

    if st.button("🚀 Generate", type="primary", use_container_width=True):
        if not prompt.strip():
            st.warning("Enter a prompt first")
        else:
            with st.spinner("Routing through providers..."):
                start = time.time()
                result = api_post("/generate", {
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "use_cache": use_cache,
                })
                elapsed = time.time() - start

            if result.get("response"):
                # Show metadata
                meta_cols = st.columns(4)
                meta_cols[0].metric("Provider", result.get("provider", "N/A"))
                meta_cols[1].metric("Model", result.get("model", "N/A"))
                meta_cols[2].metric("Attempts", result.get("attempts", 0))
                meta_cols[3].metric("Latency", f"{elapsed:.1f}s")

                if result.get("cached"):
                    st.info("⚡ Response served from cache")

                st.divider()
                st.markdown("**Response:**")
                st.markdown(result["response"])
            elif result.get("error"):
                st.error(f"All providers failed: {result['error']}")

# ---------- Tab 2: Provider Status ----------

with tab2:
    st.subheader("Configured Providers")

    if providers:
        # Show free providers
        st.markdown("### 🆓 Free Tier")
        free_providers = [p for p in providers if p["tier"] == "free"]
        if free_providers:
            for p in free_providers:
                status = "🟢 Active" if p["has_key"] and p["enabled"] else "🔴 Inactive"
                key_status = "✅ Key set" if p["has_key"] else "❌ No key"
                st.markdown(
                    f"**{p['name']}** — {status} | {key_status} | "
                    f"Model: `{p['selected_model'] or 'None'}` | Priority: {p['priority']}"
                )
        else:
            st.info("No free providers configured")

        st.markdown("### 💰 Paid Tier (Fallback)")
        paid_providers = [p for p in providers if p["tier"] == "paid"]
        if paid_providers:
            for p in paid_providers:
                status = "🟢 Active" if p["has_key"] and p["enabled"] else "🔴 Inactive"
                key_status = "✅ Key set" if p["has_key"] else "❌ No key"
                st.markdown(
                    f"**{p['name']}** — {status} | {key_status} | "
                    f"Model: `{p['selected_model'] or 'None'}` | Priority: {p['priority']}"
                )
        else:
            st.info("No paid providers configured")

    # Show failover order
    st.divider()
    st.markdown("### 🔄 Current Failover Order")
    st.caption("Drag to reorder. Free and paid providers are ordered separately.")

    active = [p for p in providers if p["has_key"] and p["enabled"]]
    free_active = sorted([p for p in active if p["tier"] == "free"], key=lambda x: x["priority"])
    paid_active = sorted([p for p in active if p["tier"] == "paid"], key=lambda x: x["priority"])

    if free_active or paid_active:
        # --- Free tier reorder ---
        if free_active:
            st.markdown("**🆓 Free Tier Order:**")
            free_col1, free_col2 = st.columns([3, 1])
            with free_col1:
                for i, p in enumerate(free_active):
                    cols = st.columns([1, 6, 2, 2])
                    cols[0].markdown(f"**{i+1}.**")
                    cols[1].markdown(f"**{p['name']}** → `{p['selected_model']}`")
                    if i > 0:
                        if cols[2].button("⬆️", key=f"up_free_{p['id']}"):
                            # Swap with previous
                            order = [x["id"] for x in free_active]
                            order[i], order[i-1] = order[i-1], order[i]
                            api_post("/providers/reorder", {"order": order})
                            st.rerun()
                    else:
                        cols[2].write("")
                    if i < len(free_active) - 1:
                        if cols[3].button("⬇️", key=f"down_free_{p['id']}"):
                            # Swap with next
                            order = [x["id"] for x in free_active]
                            order[i], order[i+1] = order[i+1], order[i]
                            api_post("/providers/reorder", {"order": order})
                            st.rerun()

        # --- Paid tier reorder ---
        if paid_active:
            st.markdown("**💰 Paid Tier Order:**")
            for i, p in enumerate(paid_active):
                cols = st.columns([1, 6, 2, 2])
                cols[0].markdown(f"**{i+1}.**")
                cols[1].markdown(f"**{p['name']}** → `{p['selected_model']}`")
                if i > 0:
                    if cols[2].button("⬆️", key=f"up_paid_{p['id']}"):
                        order = [x["id"] for x in paid_active]
                        order[i], order[i-1] = order[i-1], order[i]
                        api_post("/providers/reorder", {"order": order})
                        st.rerun()
                else:
                    cols[2].write("")
                if i < len(paid_active) - 1:
                    if cols[3].button("⬇️", key=f"down_paid_{p['id']}"):
                        order = [x["id"] for x in paid_active]
                        order[i], order[i+1] = order[i+1], order[i]
                        api_post("/providers/reorder", {"order": order})
                        st.rerun()
    else:
        st.warning("No active providers. Add API keys in the sidebar to get started.")

# ---------- Tab 3: Failover Logs ----------

with tab3:
    st.subheader("Recent Failover Logs")

    logs_data = api_get("/logs")
    logs = logs_data.get("logs", [])
    stats = logs_data.get("stats", {})

    if stats:
        stat_cols = st.columns(4)
        stat_cols[0].metric("Total Attempts", stats.get("total_attempts", 0))
        stat_cols[1].metric("Success Rate", f"{stats.get('success_rate', 0)}%")
        stat_cols[2].metric("Failover Chains", stats.get("total_failover_chains", 0))
        stat_cols[3].metric("Cache Size", api_get("/health").get("cache_size", 0))

        # Per-provider breakdown
        provider_stats = stats.get("providers_used", {})
        if provider_stats:
            st.markdown("**Per-Provider Stats:**")
            for pname, pcounts in provider_stats.items():
                total = pcounts["success"] + pcounts["failure"]
                rate = round(pcounts["success"] / total * 100, 1) if total > 0 else 0
                st.markdown(f"- **{pname}**: {pcounts['success']}/{total} successful ({rate}%)")

    st.divider()

    if logs:
        for log in logs:
            icon = "✅" if log["success"] else "❌"
            cached = " ⚡cached" if log.get("cached") else ""
            with st.expander(
                f"{icon} [{log['request_id']}] → {log.get('final_provider', 'FAILED')}"
                f" ({log['total_latency_ms']:.0f}ms){cached}"
            ):
                st.text(f"Prompt: {log['prompt_preview']}")
                st.text(f"Total attempts: {len(log['attempts'])}")
                for i, attempt in enumerate(log["attempts"], 1):
                    status_icon = "✅" if attempt["status"] == "success" else "❌"
                    st.markdown(
                        f"  {i}. {status_icon} **{attempt['provider']}** / `{attempt['model']}` "
                        f"— {attempt['status']} ({attempt['latency_ms']}ms)"
                    )
                    if attempt.get("error_message"):
                        st.caption(f"     Error: {attempt['error_message'][:200]}")
    else:
        st.info("No logs yet. Send a prompt to see failover activity.")
