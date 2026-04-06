"""
app/services/metrics_tracker.py — Post-Publish Impact Tracker & Adaptive Re-Planner (FR-7).

Polls published posts for engagement metrics and proactively surfaces
calendar adaptation suggestions when performance deviates from expectations.
"""
from __future__ import annotations
import json
import httpx
from datetime import datetime, timedelta
from app.config import get_settings
from app.utils.logger import log

settings = get_settings()


# ── Engagement thresholds ─────────────────────────────────────────────────────

ENGAGEMENT_THRESHOLDS = {
    "high":   {"reactions": 300, "comments": 50, "shares": 80},
    "medium": {"reactions": 100, "comments": 15, "shares": 20},
    "low":    {"reactions": 20,  "comments": 3,  "shares": 5},
}


def compute_engagement_score(reactions: int, comments: int, shares: int) -> int:
    """
    Weighted engagement score.
    Comments weight 3x (high intent), shares 5x (amplification), reactions 1x.
    """
    return reactions + (comments * 3) + (shares * 5)


def classify_performance(score: int, expected: str) -> str:
    """
    Classifies actual vs expected performance.
    Returns: 'exceeded' | 'met' | 'underperformed'
    """
    thresholds = ENGAGEMENT_THRESHOLDS.get(expected, ENGAGEMENT_THRESHOLDS["medium"])
    expected_score = compute_engagement_score(
        thresholds["reactions"],
        thresholds["comments"],
        thresholds["shares"],
    )
    if score >= expected_score * 1.5:
        return "exceeded"
    if score >= expected_score * 0.7:
        return "met"
    return "underperformed"


# ── Twitter Metrics Poller ────────────────────────────────────────────────────

class TwitterMetricsPoller:
    """Polls X API v2 for tweet engagement metrics."""

    BASE_URL = "https://api.twitter.com/2"

    def __init__(self):
        self._available = bool(settings.twitter_bearer_token)

    def poll_tweet(self, tweet_id: str) -> dict | None:
        """
        Returns engagement metrics for a tweet, or None if unavailable.
        """
        if not self._available:
            log.info("metrics_poller.twitter_unavailable")
            return None

        try:
            resp = httpx.get(
                f"{self.BASE_URL}/tweets/{tweet_id}",
                params={"tweet.fields": "public_metrics"},
                headers={"Authorization": f"Bearer {settings.twitter_bearer_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            pm = resp.json().get("data", {}).get("public_metrics", {})
            return {
                "impressions": pm.get("impression_count", 0),
                "reactions": pm.get("like_count", 0),
                "comments": pm.get("reply_count", 0),
                "shares": pm.get("retweet_count", 0),
            }
        except Exception as exc:
            log.error("metrics_poller.twitter_error", tweet_id=tweet_id, error=str(exc))
            return None


# ── LinkedIn Metrics Poller ───────────────────────────────────────────────────

class LinkedInMetricsPoller:
    """Polls LinkedIn UGC API for post engagement metrics."""

    STATS_URL = "https://api.linkedin.com/v2/socialActions/{post_id}"

    def __init__(self):
        self._available = bool(settings.linkedin_access_token)

    def poll_post(self, post_id: str) -> dict | None:
        if not self._available:
            log.info("metrics_poller.linkedin_unavailable")
            return None

        try:
            resp = httpx.get(
                f"https://api.linkedin.com/v2/socialActions/{post_id}",
                headers={
                    "Authorization": f"Bearer {settings.linkedin_access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "impressions": 0,  # Requires special analytics endpoint
                "reactions": data.get("likesSummary", {}).get("totalLikes", 0),
                "comments": data.get("commentsSummary", {}).get("totalFirstLevelComments", 0),
                "shares": data.get("sharesSummary", {}).get("totalShares", 0),
            }
        except Exception as exc:
            log.error("metrics_poller.linkedin_error", post_id=post_id, error=str(exc))
            return None


# ── Adaptive Re-Planner ───────────────────────────────────────────────────────

class AdaptivePlanner:
    """
    Analyses post performance data and generates calendar adaptation suggestions.
    Called by FR-7 after engagement metrics are recorded.
    """

    def analyse(
        self,
        post_performance: list[dict],
        remaining_calendar_entries: list[dict],
    ) -> list[dict]:
        """
        post_performance: list of {topic, platform, score, expected_engagement, performance_class}
        remaining_calendar_entries: list of calendar entry dicts not yet published

        Returns list of suggestions: [{entry_day, reason, suggested_change}]
        """
        if not post_performance:
            return []

        suggestions = []

        # Find top performers
        exceeded = [p for p in post_performance if p.get("performance_class") == "exceeded"]
        underperformed = [p for p in post_performance if p.get("performance_class") == "underperformed"]

        # Suggest amplifying top-performing themes
        for perf in exceeded[:2]:
            topic = perf.get("topic", "")
            for entry in remaining_calendar_entries[:5]:  # Look at next 5 entries
                if entry.get("status") == "planned":
                    suggestions.append({
                        "entry_day": entry.get("day"),
                        "current_topic": entry.get("topic"),
                        "reason": (
                            f"'{topic}' significantly exceeded engagement expectations "
                            f"(score: {perf['score']}). Amplifying this theme."
                        ),
                        "suggested_change": (
                            f"Consider replacing or supplementing with another angle on '{topic}' "
                            f"— your audience is clearly hungry for this content."
                        ),
                        "priority": "high",
                    })
                    break  # One suggestion per top performer

        # Suggest pivoting away from underperformers
        for perf in underperformed[:1]:
            topic = perf.get("topic", "")
            platform = perf.get("platform", "")
            suggestions.append({
                "entry_day": None,
                "current_topic": topic,
                "reason": (
                    f"'{topic}' on {platform} underperformed. "
                    "Consider adjusting format or timing for similar upcoming posts."
                ),
                "suggested_change": (
                    f"If you have similar topics upcoming, try switching format "
                    f"(e.g., if it was a short post, try a thread or carousel instead)."
                ),
                "priority": "medium",
            })

        log.info(
            "adaptive_planner.suggestions",
            exceeded=len(exceeded),
            underperformed=len(underperformed),
            suggestions=len(suggestions),
        )
        return suggestions

    def format_summary(self, post_performance: list[dict]) -> str:
        """Returns a human-readable performance summary string."""
        if not post_performance:
            return "No performance data available yet."

        total = len(post_performance)
        exceeded = sum(1 for p in post_performance if p.get("performance_class") == "exceeded")
        met = sum(1 for p in post_performance if p.get("performance_class") == "met")
        under = sum(1 for p in post_performance if p.get("performance_class") == "underperformed")
        avg_score = sum(p.get("score", 0) for p in post_performance) / total

        return (
            f"{total} posts tracked — "
            f"{exceeded} exceeded expectations, {met} met expectations, {under} underperformed. "
            f"Average engagement score: {avg_score:.0f}."
        )


# ── Metrics Service (orchestrates polling + analysis) ────────────────────────

class MetricsService:
    """
    High-level service that:
    1. Polls platform APIs for fresh engagement data
    2. Scores and classifies performance
    3. Runs adaptive re-planning suggestions
    """

    def __init__(self):
        self.twitter_poller = TwitterMetricsPoller()
        self.linkedin_poller = LinkedInMetricsPoller()
        self.planner = AdaptivePlanner()

    def poll_and_record(
        self,
        post_id: str,
        platform: str,
        platform_post_id: str,
    ) -> dict | None:
        """
        Polls the platform for fresh metrics.
        Returns metrics dict or None if unavailable.
        """
        if platform == "twitter":
            return self.twitter_poller.poll_tweet(platform_post_id)
        elif platform == "linkedin":
            return self.linkedin_poller.poll_post(platform_post_id)
        else:
            log.warning("metrics_service.unknown_platform", platform=platform)
            return None

    def score_and_classify(
        self,
        reactions: int,
        comments: int,
        shares: int,
        expected_engagement: str = "medium",
    ) -> dict:
        """Computes score and performance class for a post."""
        score = compute_engagement_score(reactions, comments, shares)
        performance_class = classify_performance(score, expected_engagement)
        return {"score": score, "performance_class": performance_class}

    def get_adaptive_suggestions(
        self,
        post_performance_list: list[dict],
        remaining_entries: list[dict],
    ) -> dict:
        """
        Returns suggestions dict with summary and individual suggestions.
        """
        suggestions = self.planner.analyse(post_performance_list, remaining_entries)
        summary = self.planner.format_summary(post_performance_list)
        return {
            "summary": summary,
            "suggestions": suggestions,
            "count": len(suggestions),
        }
