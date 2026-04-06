# User Guide — Autonomous Social Media Growth Agent

## Overview

This guide walks through every screen in the Streamlit UI.
Open `http://localhost:8501` after running `docker-compose up`.

---

## Page 1: Setup & Pipeline

**What it does:** Creates your user account and runs the full
Profile → Competitor → Calendar pipeline in one click.

**Steps:**

1. Fill in your name and (optionally) LinkedIn/X URLs
2. Click **Create User** — you'll see your User ID
3. Choose **Use mock data** (recommended for demo — no API keys needed)
4. Set calendar duration (default 14 days)
5. Click **Run Full Pipeline**

The system will:
- Analyse your writing style, tone, and top topics (Profile Agent)
- Discover 3–5 competitor profiles and identify content gaps (Competitor Agent)
- Generate a data-driven 14-day content calendar (Planner Agent)

You'll see a calendar preview and a link to Calendar Review.

---

## Page 2: Calendar Review

**What it does:** Shows your full calendar and lets you edit it
conversationally before locking it for content generation.

**How to use the chat:**

| What you want | Example message |
|---------------|-----------------|
| Change a topic | `"Replace Day 3 with a post about LangGraph"` |
| Move a post | `"Move the thread from Day 7 to Friday"` |
| Change a format | `"Make Day 5 a carousel instead of a long post"` |
| Add a theme | `"Add more content about production AI deployment"` |
| Approve | `"approve"` or `"looks good"` or `"lock it"` |

The AI will apply **only the change you requested** — it won't
regenerate the whole calendar.

Once you say **approve**, the calendar is locked and content
generation becomes available.

---

## Page 3: Content Review

**What it does:** Generates copy, hashtags, and visual prompts
for every calendar entry, then lets you review and refine each.

**Steps:**

1. Click **Generate All Content** (calendar must be approved first)
2. For each post, expand the entry and review three tabs:
   - **Copy** — the full post body text
   - **Hashtags** — platform-optimised hashtag sets
   - **Visual** — a detailed image generation prompt

**For each component you can:**
- ✅ **Approve** — mark it as ready to publish
- 🔄 **Regenerate** — create a new version (optionally add an instruction)
  - Example instruction for copy: `"Make it more casual and add a personal anecdote"`
  - Example instruction for visual: `"Focus on data and charts, not people"`

Only the requested component is regenerated — not the full post.

---

## Page 4: Publish

**What it does:** Publishes approved posts to Twitter/X and/or
LinkedIn, or copies content to clipboard for manual posting.

**API status indicator** at the top shows:
- 🟢 **Live** — will publish directly via API
- 🟡 **Clipboard** — API not configured; shows formatted content to copy

**Publishing:**
1. Find the post you want to publish
2. Click **Publish to [Platform]**
3. If API is live: you'll see a success message with the post URL
4. If API is unavailable: a text box appears with the formatted content ready to copy

**Clipboard mode** is full fallback — you always get your content
even without API keys configured.

---

## Page 5: Analytics

**What it does:** Tracks engagement on published posts and
suggests calendar adaptations based on performance.

**Recording metrics:**
1. Select a published post from the dropdown
2. Enter the engagement numbers (from the platform's analytics)
3. Click **Record Metrics**

**Adaptive suggestions:**
After recording metrics, the system analyses performance and suggests:
- **Amplify** high-performing topics in remaining calendar entries
- **Pivot** away from underperforming topics or formats

Example suggestion:
> "RAG systems significantly exceeded engagement expectations (score: 800). 
> Consider more content on this theme for Day 9."

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "API not reachable" in sidebar | Backend is starting up — wait 30s and refresh |
| Pipeline fails | Check `GROQ_API_KEY` is set in `.env` |
| "Run pipeline first" warning | Complete Step 1 (Setup page) |
| Content not generating | Calendar must be **approved/locked** first |
| Publish fails | Check Twitter/LinkedIn API keys in `.env`, or use clipboard mode |
| Database errors | Run `docker-compose down -v && docker-compose up --build` to reset |

---

## API Keys (Optional)

The system works fully in demo mode with no API keys except Groq.

| Key | Where to get | Required? |
|-----|-------------|-----------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | **Yes** |
| `TWITTER_*` | [developer.twitter.com](https://developer.twitter.com) | No (clipboard fallback) |
| `LINKEDIN_*` | [linkedin.com/developers](https://www.linkedin.com/developers/) | No (clipboard fallback) |
| `PROXYCURL_API_KEY` | [nubela.co/proxycurl](https://nubela.co/proxycurl) | No (mock data fallback) |
