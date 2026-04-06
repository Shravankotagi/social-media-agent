"""
scripts/seed_demo.py — Seeds the database with demo data for a walkthrough.

Usage (inside Docker or local venv):
    python scripts/seed_demo.py

Creates a demo user, runs the full pipeline with mock data,
and prints the IDs needed for the Streamlit demo.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
import json

BASE_URL = "http://localhost:8000/api/v1"


def post(path: str, body: dict):
    resp = httpx.post(f"{BASE_URL}{path}", json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()


def main():
    print("🌱 Seeding demo data...\n")

    # 1. Create user
    user = post("/users", {
        "name": "Alex Chen",
        "linkedin_url": "https://linkedin.com/in/alexchen-ai",
        "twitter_url": "https://x.com/alexchen_ai",
    })
    user_id = user["id"]
    print(f"✅ User created: {user_id}")

    # 2. Run full pipeline
    print("⏳ Running full pipeline (Profile → Competitor → Calendar)...")
    pipeline = post("/pipeline/run", {
        "user_id": user_id,
        "days": 14,
        "use_mock": True,
    })
    calendar_id = pipeline["calendar_id"]
    print(f"✅ Pipeline complete")
    print(f"   Profile Report ID: {pipeline['profile_report_id']}")
    print(f"   Competitor Report ID: {pipeline['competitor_report_id']}")
    print(f"   Calendar ID: {calendar_id}")
    print(f"   Status: {pipeline['calendar_status']}")

    print(f"\n📋 Calendar preview:")
    for entry in pipeline["calendar"]["entries"][:5]:
        print(f"   Day {entry['day']}: [{entry['platform'].upper()}] {entry['topic'][:50]}")
    print(f"   ...and {len(pipeline['calendar']['entries']) - 5} more entries")

    print(f"\n{'='*60}")
    print(f"🚀 Open Streamlit at http://localhost:8501")
    print(f"   Use these IDs if needed:")
    print(f"   User ID:     {user_id}")
    print(f"   Calendar ID: {calendar_id}")
    print(f"{'='*60}")
    print(f"\n💡 Next steps in the UI:")
    print(f"   1. Go to 'Calendar Review' → chat to edit or just say 'approve'")
    print(f"   2. Go to 'Content Review' → click 'Generate All Content'")
    print(f"   3. Review, approve, and publish from 'Publish' page")


if __name__ == "__main__":
    main()
