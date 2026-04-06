"""
frontend/app.py — Streamlit UI for the Autonomous Social Media Growth Agent.

Pages:
  1. Setup — create user, run full pipeline
  2. Calendar Review — HITL editing with chat interface
  3. Content Review — per-post review with targeted regeneration
  4. Publish — publish or copy to clipboard
  5. Analytics — engagement metrics + adaptive suggestions
"""
import streamlit as st
import httpx
import os
import json
from datetime import datetime

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000") + "/api/v1"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Social Media Growth Agent",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stButton>button { border-radius: 8px; }
    .metric-card {
        background: #1e1e2e;
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid #2d2d3e;
        margin-bottom: 0.5rem;
    }
    .status-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.8em;
        font-weight: 600;
    }
    .badge-pending { background: #fbbf2420; color: #fbbf24; }
    .badge-approved { background: #10b98120; color: #10b981; }
    .badge-locked { background: #3b82f620; color: #3b82f6; }
    .badge-posted { background: #10b98120; color: #10b981; }
    .chat-user { background: #1e3a5f; border-radius: 8px; padding: 8px 12px; margin: 4px 0; }
    .chat-assistant { background: #1e2d1e; border-radius: 8px; padding: 8px 12px; margin: 4px 0; }
</style>
""", unsafe_allow_html=True)


# ── API helpers ───────────────────────────────────────────────────────────────

def api(method: str, path: str, **kwargs):
    try:
        resp = httpx.request(method, f"{API_BASE}{path}", timeout=300, **kwargs)
        resp.raise_for_status()
        return resp.json(), None
    except httpx.HTTPStatusError as e:
        try:
            return None, e.response.text
        except Exception:
            return None, str(e)
    except httpx.TimeoutException:
        return None, "Request timed out — content generation is still running. Wait 30 seconds and refresh."
    except Exception as e:
        return None, str(e)


def get(path: str):
    return api("GET", path)


def post(path: str, body: dict):
    return api("POST", path, json=body)


# ── Sidebar navigation ────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🚀 Social Media Agent")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["🏠 Setup & Pipeline", "📅 Calendar Review", "✍️ Content Review", "📤 Publish", "📊 Analytics"],
    )
    st.markdown("---")

    # Health check
    health, err = get("/health")
    if health:
        st.markdown("**System Status**")
        st.markdown(f"{'🟢' if health['database'] else '🔴'} Database")
        st.markdown(f"{'🟢' if health['chromadb'] else '🔴'} ChromaDB")
        st.markdown(f"{'🟢' if health['twitter_api'] else '🟡'} Twitter API {'(clipboard mode)' if not health['twitter_api'] else ''}")
        st.markdown(f"{'🟢' if health['linkedin_api'] else '🟡'} LinkedIn API {'(clipboard mode)' if not health['linkedin_api'] else ''}")
    else:
        st.warning("⚠️ API not reachable")

    st.markdown("---")
    if "user_id" in st.session_state:
        st.success(f"👤 User: {st.session_state.get('user_name', st.session_state['user_id'][:8])}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1: Setup & Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

if page == "🏠 Setup & Pipeline":
    st.title("🏠 Setup & Pipeline")
    st.markdown("Create your user profile and run the full AI pipeline to generate a content calendar.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. Create User")
        with st.form("user_form"):
            name = st.text_input("Your Name", value="Alex Chen")
            linkedin = st.text_input("LinkedIn URL (optional)", value="https://linkedin.com/in/alexchen-ai")
            twitter = st.text_input("X/Twitter URL (optional)", value="https://x.com/alexchen_ai")
            create_btn = st.form_submit_button("Create User")

        if create_btn:
            data, err = post("/users", {"name": name, "linkedin_url": linkedin, "twitter_url": twitter})
            if data:
                st.session_state["user_id"] = data["id"]
                st.session_state["user_name"] = name
                st.success(f"✅ User created! ID: `{data['id']}`")
            else:
                st.error(f"Error: {err}")

    with col2:
        st.subheader("2. Run Full Pipeline")
        if "user_id" not in st.session_state:
            st.info("Create a user first.")
        else:
            use_mock = st.checkbox("Use mock data (demo mode)", value=True)
            days = st.slider("Calendar duration (days)", 7, 30, 14)

            if st.button("🚀 Run Full Pipeline", type="primary"):
                with st.spinner("Running Profile → Competitor → Calendar agents..."):
                    data, err = post("/pipeline/run", {
                        "user_id": st.session_state["user_id"],
                        "days": days,
                        "use_mock": use_mock,
                    })

                if data:
                    st.session_state["calendar_id"] = data["calendar_id"]
                    st.session_state["profile_report_id"] = data["profile_report_id"]
                    st.success("✅ Pipeline complete!")
                    st.info(data["message"])

                    with st.expander("📋 Calendar Preview"):
                        entries = data["calendar"].get("entries", [])
                        for e in entries[:7]:
                            st.markdown(
                                f"**Day {e['day']}** ({e['date']}) — `{e['platform'].upper()}` — "
                                f"{e['topic']} _{e.get('format', '')}_"
                            )
                        if len(entries) > 7:
                            st.caption(f"...and {len(entries)-7} more entries. Go to Calendar Review.")
                else:
                    st.error(f"Pipeline failed: {err}")

    if "calendar_id" in st.session_state:
        st.markdown("---")
        st.success(f"📅 Active Calendar ID: `{st.session_state['calendar_id']}`")
        st.info("👉 Go to **Calendar Review** to refine it and approve before generating content.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2: Calendar Review (HITL)
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📅 Calendar Review":
    st.title("📅 Calendar Review")
    st.markdown("Chat with the AI to edit your calendar. Say **'approve'** to lock it.")

    if "calendar_id" not in st.session_state:
        st.warning("Run the pipeline first (Setup page).")
    else:
        calendar_id = st.session_state["calendar_id"]

        # Load current calendar
        cal_data, err = get(f"/calendar/{calendar_id}")
        if err:
            st.error(f"Could not load calendar: {err}")
        else:
            status = cal_data["status"]
            calendar = cal_data["calendar"]

            # Status badge
            badge_class = {"draft": "badge-pending", "under_review": "badge-pending",
                           "approved": "badge-approved", "locked": "badge-locked"}.get(status, "")
            st.markdown(f"Status: <span class='status-badge {badge_class}'>{status.upper()}</span>", unsafe_allow_html=True)

            col_cal, col_chat = st.columns([1.2, 1])

            with col_cal:
                st.subheader("Current Calendar")
                entries = calendar.get("entries", [])
                for e in entries:
                    with st.expander(f"Day {e['day']} — {e['platform'].upper()} — {e['topic'][:50]}"):
                        st.write(f"**Format:** {e.get('format', '—')}")
                        st.write(f"**Date:** {e.get('date', '—')} at {e.get('posting_time', '—')}")
                        st.write(f"**Rationale:** {e.get('rationale', '—')}")
                        st.write(f"**Expected engagement:** {e.get('expected_engagement', '—')}")

            with col_chat:
                st.subheader("Edit Calendar")
                if status == "locked":
                    st.success("✅ Calendar is locked and approved!")
                    if st.button("Generate Content Now →", type="primary"):
                        st.session_state["goto_content_gen"] = True
                else:
                    # Chat history
                    if "chat_history" not in st.session_state:
                        st.session_state["chat_history"] = []

                    for msg in st.session_state["chat_history"]:
                        css_class = "chat-user" if msg["role"] == "user" else "chat-assistant"
                        label = "You" if msg["role"] == "user" else "AI"
                        st.markdown(f"<div class='{css_class}'><b>{label}:</b> {msg['content']}</div>", unsafe_allow_html=True)

                    st.markdown("**Examples:** 'Replace Day 3 with a post about LangGraph' · 'Move Day 7 thread to Friday' · 'approve'")

                    with st.form("chat_form", clear_on_submit=True):
                        user_msg = st.text_input("Your message", placeholder="Edit or approve...")
                        send = st.form_submit_button("Send")

                    if send and user_msg:
                        st.session_state["chat_history"].append({"role": "user", "content": user_msg})
                        with st.spinner("Applying change..."):
                            data, err = post("/calendar/edit", {
                                "calendar_id": calendar_id,
                                "user_id": st.session_state.get("user_id", ""),
                                "message": user_msg,
                            })
                        if data:
                            st.session_state["chat_history"].append(
                                {"role": "assistant", "content": data["assistant_response"]}
                            )
                            if data["is_locked"]:
                                st.success("✅ Calendar locked!")
                        else:
                            st.error(f"Error: {err}")
                        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3: Content Review
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "✍️ Content Review":
    st.title("✍️ Content Review")

    if "calendar_id" not in st.session_state:
        st.warning("Run the pipeline first.")
    else:
        calendar_id = st.session_state["calendar_id"]
        user_id = st.session_state.get("user_id", "")

        # Generate content button
        cal_data, _ = get(f"/calendar/{calendar_id}")
        cal_status = cal_data["status"] if cal_data else "unknown"

        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"Calendar status: **{cal_status}**")
        with col2:
            if cal_status in ("approved", "locked") and st.button("⚡ Generate All Content", type="primary"):
                st.info(f"Generating for calendar: {calendar_id} user: {user_id}")
                with st.spinner("Running content pipeline — this takes 2-3 minutes..."):
                    data, err = post("/content/generate", {
                        "calendar_id": calendar_id,
                        "user_id": user_id,
                    })
                if data:
                    st.success(f"✅ Generated {data['count']} posts!")
                    st.rerun()
                else:
                    st.error(f"Generation failed: {err}")
            elif cal_status not in ("approved", "locked"):
                st.info("Approve calendar first (Calendar Review page).")

        # Load posts
        posts_data, err = get(f"/content/calendar/{calendar_id}/posts")
        if err or not posts_data:
            st.info("No content generated yet. Generate content above.")
        else:
            posts = posts_data.get("posts", [])
            if not posts:
                st.info("No posts found. Click 'Generate All Content' above.")
            else:
                st.markdown(f"**{len(posts)} posts generated**")
                for p in posts:
                    with st.expander(
                        f"Day {p['day']} — {p['platform'].upper()} — {p['topic'][:50]} "
                        f"[{p.get('publish_status','draft').upper()}]"
                    ):
                        tabs = st.tabs(["Copy", "Hashtags", "Visual"])

                        with tabs[0]:
                            st.markdown(p.get("body_copy", "_Not generated_"))
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Approve Copy", key=f"approve_copy_{p['post_id']}"):
                                    post("/content/approve", {"post_id": p["post_id"], "component": "copy"})
                                    st.success("Approved!")
                            with c2:
                                regen_inst = st.text_input("Instruction (optional)", key=f"copy_inst_{p['post_id']}")
                                if st.button("🔄 Regenerate Copy", key=f"regen_copy_{p['post_id']}"):
                                    with st.spinner("Regenerating..."):
                                        post("/content/regenerate", {
                                            "post_id": p["post_id"],
                                            "component": "copy",
                                            "instruction": regen_inst,
                                        })
                                    st.rerun()

                        with tabs[1]:
                            st.markdown(p.get("hashtags", "_Not generated_"))
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Approve Hashtags", key=f"approve_ht_{p['post_id']}"):
                                    post("/content/approve", {"post_id": p["post_id"], "component": "hashtags"})
                                    st.success("Approved!")
                            with c2:
                                if st.button("🔄 Regenerate Hashtags", key=f"regen_ht_{p['post_id']}"):
                                    with st.spinner("Regenerating..."):
                                        post("/content/regenerate", {"post_id": p["post_id"], "component": "hashtags"})
                                    st.rerun()

                        with tabs[2]:
                            st.markdown(f"**Prompt:** {p.get('visual_prompt', '_Not generated_')}")
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Approve Visual", key=f"approve_vis_{p['post_id']}"):
                                    post("/content/approve", {"post_id": p["post_id"], "component": "visual"})
                                    st.success("Approved!")
                            with c2:
                                regen_inst = st.text_input("Instruction (optional)", key=f"vis_inst_{p['post_id']}")
                                if st.button("🔄 Regenerate Visual", key=f"regen_vis_{p['post_id']}"):
                                    with st.spinner("Regenerating..."):
                                        post("/content/regenerate", {
                                            "post_id": p["post_id"],
                                            "component": "visual",
                                            "instruction": regen_inst,
                                        })
                                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4: Publish
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📤 Publish":
    st.title("📤 Publish")
    st.markdown("Publish your approved posts or copy to clipboard for manual posting.")

    if "calendar_id" not in st.session_state:
        st.warning("Run the pipeline first.")
    else:
        posts_data, err = get(f"/content/calendar/{st.session_state['calendar_id']}/posts")
        if err or not posts_data:
            st.info("No posts to publish. Generate content first.")
        else:
            posts = [p for p in posts_data.get("posts", []) if p.get("body_copy")]

            if not posts:
                st.info("No posts with generated content found.")
            else:
                pub_status, _ = get("/publish/status")
                if pub_status:
                    c1, c2 = st.columns(2)
                    c1.metric("Twitter API", "🟢 Live" if pub_status["twitter_api"] else "🟡 Clipboard")
                    c2.metric("LinkedIn API", "🟢 Live" if pub_status["linkedin_api"] else "🟡 Clipboard")
                st.markdown("---")

                for p in posts:
                    if p.get("publish_status") == "posted":
                        st.success(f"✅ Day {p['day']} — {p['topic'][:40]} — POSTED")
                        continue

                    with st.expander(f"Day {p['day']} — {p['platform'].upper()} — {p['topic'][:50]}"):
                        st.markdown(p.get("body_copy", "")[:500])
                        st.caption(p.get("hashtags", ""))

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"📤 Publish to {p['platform'].title()}", key=f"pub_{p['post_id']}"):
                                with st.spinner("Publishing..."):
                                    result, err = post("/publish", {"post_id": p["post_id"]})
                                if result:
                                    for plat, r in result.get("results", {}).items():
                                        if r.get("success"):
                                            st.success(f"✅ Posted to {plat}!")
                                        elif r.get("mode") == "clipboard":
                                            st.warning(f"📋 {plat}: API unavailable — copy content below")
                                            st.code(r.get("content", ""))
                                        else:
                                            st.error(f"❌ {plat}: {r.get('error', 'Unknown error')}")
                                else:
                                    st.error(f"Error: {err}")
                        with col2:
                            if st.button("📋 Copy to Clipboard", key=f"clip_{p['post_id']}"):
                                full = f"{p.get('body_copy','')}\n\n{p.get('hashtags','')}"
                                st.code(full)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5: Analytics
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📊 Analytics":
    st.title("📊 Analytics & Adaptive Planning")
    st.markdown("Track post performance and get AI-powered suggestions to improve your remaining calendar.")

    if "calendar_id" not in st.session_state:
        st.warning("Run the pipeline first.")
    else:
        calendar_id = st.session_state["calendar_id"]

        # Record metrics form
        st.subheader("Record Engagement Metrics")
        posts_data, _ = get(f"/content/calendar/{calendar_id}/posts")
        posts = [p for p in (posts_data or {}).get("posts", []) if p.get("publish_status") == "posted"]

        if posts:
            with st.form("metrics_form"):
                post_labels = {f"Day {p['day']} — {p['topic'][:40]}": p["post_id"] for p in posts}
                selected = st.selectbox("Select published post", list(post_labels.keys()))
                col1, col2, col3, col4 = st.columns(4)
                impressions = col1.number_input("Impressions", 0, value=500)
                reactions = col2.number_input("Reactions", 0, value=45)
                comments = col3.number_input("Comments", 0, value=12)
                shares = col4.number_input("Shares", 0, value=8)
                if st.form_submit_button("Record Metrics"):
                    data, err = post("/metrics/record", {
                        "post_id": post_labels[selected],
                        "impressions": impressions,
                        "reactions": reactions,
                        "comments": comments,
                        "shares": shares,
                    })
                    if data:
                        st.success("Metrics recorded!")
                    else:
                        st.error(err)
        else:
            st.info("No published posts yet. Publish posts to track engagement.")

        # Adaptive suggestions
        st.markdown("---")
        st.subheader("Adaptive Re-planning Suggestions")
        suggestions_data, err = get(f"/metrics/adapt/{calendar_id}")
        if suggestions_data:
            suggestions = suggestions_data.get("suggestions", [])
            if suggestions:
                for s in suggestions:
                    st.markdown(f"**{s['topic']}** ({s['platform']})")
                    st.markdown(f"Engagement score: `{s['engagement_score']}` — {s['suggestion']}")
                    st.markdown("---")
            else:
                st.info(suggestions_data.get("message", "No suggestions yet. Record some metrics first."))
        else:
            st.error(f"Could not load suggestions: {err}")