"""
app/services/publisher.py — Content Publishing Service (FR-6).

Handles publishing to Twitter/X (API v2) and LinkedIn (Share API).
Graceful fallback to clipboard mode when APIs are unavailable.
"""
from __future__ import annotations
import httpx
from app.config import get_settings
from app.utils.logger import log, record_publish

settings = get_settings()


# ── Twitter / X Publisher ─────────────────────────────────────────────────────

class TwitterPublisher:
    """
    Publishes to X using the v2 API (free tier).
    Handles OAuth 1.0a user auth.
    """

    BASE_URL = "https://api.twitter.com/2"

    def __init__(self):
        self._available = bool(
            settings.twitter_api_key
            and settings.twitter_access_token
            and settings.twitter_access_secret
        )

    def is_available(self) -> bool:
        return self._available

    def post_tweet(self, text: str, hashtags: list[str] | None = None) -> dict:
        """
        Post a tweet. Appends hashtags if provided and within character limit.
        Returns {success, post_id, url, mode}.
        """
        if not self._available:
            log.info("twitter.api_unavailable_clipboard_mode")
            return self._clipboard_fallback(text, hashtags, "twitter")

        # Build tweet text
        tag_str = " ".join(f"#{h}" for h in (hashtags or []))
        full_text = f"{text}\n\n{tag_str}".strip() if tag_str else text

        # Trim to 280 chars
        if len(full_text) > 280:
            full_text = full_text[:277] + "..."

        try:
            import tweepy
            client = tweepy.Client(
                consumer_key=settings.twitter_api_key,
                consumer_secret=settings.twitter_api_secret,
                access_token=settings.twitter_access_token,
                access_token_secret=settings.twitter_access_secret,
            )
            response = client.create_tweet(text=full_text)
            tweet_id = response.data["id"]
            url = f"https://x.com/i/status/{tweet_id}"
            record_publish("twitter", True)
            log.info("twitter.posted", tweet_id=tweet_id)
            return {"success": True, "post_id": tweet_id, "url": url, "mode": "api"}
        except Exception as exc:
            log.error("twitter.post_failed", error=str(exc))
            record_publish("twitter", False)
            return self._clipboard_fallback(text, hashtags, "twitter", error=str(exc))

    def post_thread(self, tweets: list[str]) -> dict:
        """Post a thread of tweets."""
        if not self._available:
            combined = "\n\n".join(f"{i+1}/{len(tweets)} {t}" for i, t in enumerate(tweets))
            return self._clipboard_fallback(combined, [], "twitter")

        try:
            import tweepy
            client = tweepy.Client(
                consumer_key=settings.twitter_api_key,
                consumer_secret=settings.twitter_api_secret,
                access_token=settings.twitter_access_token,
                access_token_secret=settings.twitter_access_secret,
            )
            tweet_ids = []
            reply_to = None
            for tweet in tweets:
                kwargs = {"text": tweet[:280]}
                if reply_to:
                    kwargs["in_reply_to_tweet_id"] = reply_to
                resp = client.create_tweet(**kwargs)
                reply_to = resp.data["id"]
                tweet_ids.append(reply_to)

            record_publish("twitter", True)
            return {"success": True, "post_ids": tweet_ids, "mode": "api"}
        except Exception as exc:
            log.error("twitter.thread_failed", error=str(exc))
            record_publish("twitter", False)
            return self._clipboard_fallback("\n---\n".join(tweets), [], "twitter", error=str(exc))

    @staticmethod
    def _clipboard_fallback(text: str, hashtags: list | None, platform: str, error: str = "") -> dict:
        tag_str = " ".join(f"#{h}" for h in (hashtags or []))
        full_text = f"{text}\n\n{tag_str}".strip() if tag_str else text
        return {
            "success": False,
            "mode": "clipboard",
            "platform": platform,
            "content": full_text,
            "message": "API unavailable — copy content to clipboard and post manually.",
            "error": error,
        }


# ── LinkedIn Publisher ────────────────────────────────────────────────────────

class LinkedInPublisher:
    """
    Publishes to LinkedIn using the Share API (UGC Posts v2).
    """

    SHARE_URL = "https://api.linkedin.com/v2/ugcPosts"
    PROFILE_URL = "https://api.linkedin.com/v2/me"

    def __init__(self):
        self._available = bool(settings.linkedin_access_token)

    def is_available(self) -> bool:
        return self._available

    def _get_person_urn(self) -> str | None:
        """Get the authenticated user's LinkedIn URN."""
        try:
            resp = httpx.get(
                self.PROFILE_URL,
                headers={"Authorization": f"Bearer {settings.linkedin_access_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            return f"urn:li:person:{resp.json()['id']}"
        except Exception as exc:
            log.error("linkedin.profile_fetch_failed", error=str(exc))
            return None

    def post(self, text: str, hashtags: list[str] | None = None) -> dict:
        """Post to LinkedIn feed."""
        if not self._available:
            return self._clipboard_fallback(text, hashtags)

        person_urn = self._get_person_urn()
        if not person_urn:
            return self._clipboard_fallback(text, hashtags, error="Could not fetch LinkedIn profile URN")

        tag_str = " ".join(f"#{h}" for h in (hashtags or []))
        full_text = f"{text}\n\n{tag_str}".strip() if tag_str else text

        payload = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": full_text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        try:
            resp = httpx.post(
                self.SHARE_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.linkedin_access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                timeout=15,
            )
            resp.raise_for_status()
            post_id = resp.headers.get("x-restli-id", "unknown")
            record_publish("linkedin", True)
            log.info("linkedin.posted", post_id=post_id)
            return {"success": True, "post_id": post_id, "mode": "api"}
        except Exception as exc:
            log.error("linkedin.post_failed", error=str(exc))
            record_publish("linkedin", False)
            return self._clipboard_fallback(text, hashtags, error=str(exc))

    @staticmethod
    def _clipboard_fallback(text: str, hashtags: list | None = None, error: str = "") -> dict:
        tag_str = " ".join(f"#{h}" for h in (hashtags or []))
        full_text = f"{text}\n\n{tag_str}".strip() if tag_str else text
        return {
            "success": False,
            "mode": "clipboard",
            "platform": "linkedin",
            "content": full_text,
            "message": "API unavailable — copy content to clipboard and post manually.",
            "error": error,
        }


# ── Unified Publisher ─────────────────────────────────────────────────────────

class Publisher:
    """
    Unified publishing interface. Routes to the correct platform publisher
    and handles rate limiting / status tracking.
    """

    def __init__(self):
        self.twitter = TwitterPublisher()
        self.linkedin = LinkedInPublisher()

    def publish(self, platform: str, body_copy: str, hashtags: list[str], format: str = "short_post") -> dict:
        """
        Publish content to the specified platform.
        platform: 'twitter' | 'linkedin' | 'both'
        """
        results = {}

        if platform in ("twitter", "both"):
            if format == "thread":
                # Split by double newlines for thread tweets
                tweets = [t.strip() for t in body_copy.split("\n\n") if t.strip()]
                if len(tweets) > 1:
                    results["twitter"] = self.twitter.post_thread(tweets)
                else:
                    results["twitter"] = self.twitter.post_tweet(body_copy, hashtags)
            else:
                results["twitter"] = self.twitter.post_tweet(body_copy, hashtags)

        if platform in ("linkedin", "both"):
            results["linkedin"] = self.linkedin.post(body_copy, hashtags)

        return results

    def get_status(self) -> dict:
        return {
            "twitter_api": self.twitter.is_available(),
            "linkedin_api": self.linkedin.is_available(),
        }
