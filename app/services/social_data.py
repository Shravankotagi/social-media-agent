"""
app/services/social_data.py — Social profile data ingestion service (TS-2).

Fetches LinkedIn and X/Twitter profile data using:
  1. Official APIs (Twitter v2 free tier, Proxycurl for LinkedIn)
  2. Graceful fallback to curated mock/sample data when rate limits hit

All interactions comply with platform Terms of Service.
"""
from __future__ import annotations
import re
import httpx
from app.config import get_settings
from app.services.mock_data import MOCK_USER_PROFILE
from app.utils.logger import log

settings = get_settings()


# ── Twitter / X Data Fetcher ──────────────────────────────────────────────────

class TwitterDataFetcher:
    """
    Fetches public profile and recent tweets using X API v2 free tier.
    Falls back to mock data when API key is missing or rate limit is hit.
    """

    BASE_URL = "https://api.twitter.com/2"
    MAX_RESULTS = 10  # Free tier limit

    def __init__(self):
        self._available = bool(settings.twitter_bearer_token)

    def is_available(self) -> bool:
        return self._available

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {settings.twitter_bearer_token}"}

    def _extract_username(self, url_or_handle: str) -> str:
        """Extract @handle from URL or return as-is."""
        url_or_handle = url_or_handle.strip().lstrip("@")
        match = re.search(r"(?:x\.com|twitter\.com)/([^/?]+)", url_or_handle)
        return match.group(1) if match else url_or_handle

    def fetch_profile(self, url_or_handle: str) -> dict:
        """
        Fetches a Twitter user profile + recent tweets.
        Returns a normalised dict compatible with ProfileAgent.
        Falls back to mock data on any error.
        """
        if not self._available:
            log.info("twitter_fetcher.unavailable_mock_fallback")
            return self._mock_twitter_profile()

        username = self._extract_username(url_or_handle)
        try:
            # 1. Get user info
            user_resp = httpx.get(
                f"{self.BASE_URL}/users/by/username/{username}",
                params={
                    "user.fields": "public_metrics,description,created_at,url",
                },
                headers=self._headers(),
                timeout=10,
            )
            user_resp.raise_for_status()
            user_data = user_resp.json().get("data", {})
            user_id = user_data.get("id")
            metrics = user_data.get("public_metrics", {})

            # 2. Get recent tweets
            tweets_resp = httpx.get(
                f"{self.BASE_URL}/users/{user_id}/tweets",
                params={
                    "max_results": self.MAX_RESULTS,
                    "tweet.fields": "public_metrics,created_at,entities",
                    "exclude": "retweets,replies",
                },
                headers=self._headers(),
                timeout=10,
            )
            tweets_resp.raise_for_status()
            tweets = tweets_resp.json().get("data", [])

            # 3. Normalise
            posts = []
            for t in tweets:
                tm = t.get("public_metrics", {})
                posts.append({
                    "platform": "twitter",
                    "text": t.get("text", ""),
                    "likes": tm.get("like_count", 0),
                    "reposts": tm.get("retweet_count", 0),
                    "replies": tm.get("reply_count", 0),
                    "date": t.get("created_at", ""),
                    "format": self._infer_format(t.get("text", "")),
                })

            log.info("twitter_fetcher.success", username=username, tweets=len(posts))
            return {
                "name": user_data.get("name", username),
                "twitter_url": f"https://x.com/{username}",
                "bio": user_data.get("description", ""),
                "follower_count": {"twitter": metrics.get("followers_count", 0)},
                "following_count": {"twitter": metrics.get("following_count", 0)},
                "posts": posts,
                "topics": [],  # ProfileAgent will infer these
                "posting_cadence": {},
            }

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                log.warning("twitter_fetcher.rate_limit_mock_fallback", username=username)
            else:
                log.error("twitter_fetcher.http_error", status=exc.response.status_code, username=username)
            return self._mock_twitter_profile()
        except Exception as exc:
            log.error("twitter_fetcher.error", error=str(exc), username=username)
            return self._mock_twitter_profile()

    @staticmethod
    def _infer_format(text: str) -> str:
        if len(text) > 240:
            return "thread"
        if text.count("http") > 1:
            return "link_post"
        return "short_post"

    @staticmethod
    def _mock_twitter_profile() -> dict:
        """Returns realistic mock Twitter data."""
        return {
            "name": MOCK_USER_PROFILE["name"],
            "twitter_url": MOCK_USER_PROFILE["twitter_url"],
            "bio": MOCK_USER_PROFILE["bio"],
            "follower_count": {"twitter": MOCK_USER_PROFILE["follower_count"]["twitter"]},
            "following_count": {"twitter": MOCK_USER_PROFILE["following_count"]["twitter"]},
            "posts": [p for p in MOCK_USER_PROFILE["posts"] if p["platform"] == "twitter"],
            "topics": MOCK_USER_PROFILE["topics"],
            "posting_cadence": {"twitter": MOCK_USER_PROFILE["posting_cadence"]["twitter"]},
        }


# ── LinkedIn Data Fetcher ─────────────────────────────────────────────────────

class LinkedInDataFetcher:
    """
    Fetches LinkedIn profile data using Proxycurl free tier.
    Falls back to mock data when API key is missing.

    Proxycurl: https://nubela.co/proxycurl (free tier available)
    """

    BASE_URL = "https://nubela.co/proxycurl/api/v2/linkedin"

    def __init__(self):
        self._available = bool(settings.proxycurl_api_key)

    def is_available(self) -> bool:
        return self._available

    def _extract_linkedin_url(self, url: str) -> str:
        """Normalise LinkedIn URL."""
        if not url.startswith("http"):
            url = f"https://linkedin.com/in/{url}"
        return url.split("?")[0].rstrip("/")

    def fetch_profile(self, linkedin_url: str) -> dict:
        """
        Fetches a LinkedIn profile.
        Returns a normalised dict compatible with ProfileAgent.
        Falls back to mock data on any error.
        """
        if not self._available:
            log.info("linkedin_fetcher.unavailable_mock_fallback")
            return self._mock_linkedin_profile()

        url = self._extract_linkedin_url(linkedin_url)
        try:
            resp = httpx.get(
                self.BASE_URL,
                params={"url": url, "use_cache": "if-present"},
                headers={"Authorization": f"Bearer {settings.proxycurl_api_key}"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            # Normalise Proxycurl response
            posts = []
            for article in data.get("articles", [])[:10]:
                posts.append({
                    "platform": "linkedin",
                    "text": article.get("title", "") + " " + article.get("description", ""),
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "date": article.get("published_date", ""),
                    "format": "article",
                })

            log.info("linkedin_fetcher.success", url=linkedin_url)
            return {
                "name": f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
                "linkedin_url": linkedin_url,
                "bio": data.get("summary", ""),
                "headline": data.get("headline", ""),
                "follower_count": {"linkedin": data.get("follower_count", 0)},
                "following_count": {"linkedin": 0},
                "posts": posts,
                "topics": [],
                "posting_cadence": {},
                "skills": [s.get("name") for s in data.get("skills", [])[:10]],
            }

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                log.warning("linkedin_fetcher.rate_limit_mock_fallback")
            else:
                log.error("linkedin_fetcher.http_error", status=exc.response.status_code)
            return self._mock_linkedin_profile()
        except Exception as exc:
            log.error("linkedin_fetcher.error", error=str(exc))
            return self._mock_linkedin_profile()

    @staticmethod
    def _mock_linkedin_profile() -> dict:
        return {
            "name": MOCK_USER_PROFILE["name"],
            "linkedin_url": MOCK_USER_PROFILE["linkedin_url"],
            "bio": MOCK_USER_PROFILE["bio"],
            "headline": "AI/ML Engineer | Writing about LLMs and production AI",
            "follower_count": {"linkedin": MOCK_USER_PROFILE["follower_count"]["linkedin"]},
            "following_count": {"linkedin": MOCK_USER_PROFILE["following_count"]["linkedin"]},
            "posts": [p for p in MOCK_USER_PROFILE["posts"] if p["platform"] == "linkedin"],
            "topics": MOCK_USER_PROFILE["topics"],
            "posting_cadence": {"linkedin": MOCK_USER_PROFILE["posting_cadence"]["linkedin"]},
        }


# ── Combined Profile Fetcher ──────────────────────────────────────────────────

class SocialDataService:
    """
    Merges Twitter and LinkedIn data into a single profile dict
    ready for consumption by ProfileAgent.
    """

    def __init__(self):
        self.twitter = TwitterDataFetcher()
        self.linkedin = LinkedInDataFetcher()

    def fetch_combined_profile(
        self,
        linkedin_url: str | None = None,
        twitter_url: str | None = None,
        use_mock: bool = True,
    ) -> dict:
        """
        Fetches and merges profile data from both platforms.
        use_mock=True: always use mock data (for demos).
        use_mock=False: attempt live fetch, fallback to mock on failure.
        """
        if use_mock:
            log.info("social_data.using_mock_profile")
            return MOCK_USER_PROFILE

        twitter_data: dict = {}
        linkedin_data: dict = {}

        if twitter_url:
            twitter_data = self.twitter.fetch_profile(twitter_url)
        if linkedin_url:
            linkedin_data = self.linkedin.fetch_profile(linkedin_url)

        # Merge: prefer LinkedIn for name/bio, combine posts
        merged = {
            "name": linkedin_data.get("name") or twitter_data.get("name", "Unknown"),
            "linkedin_url": linkedin_url,
            "twitter_url": twitter_url,
            "bio": linkedin_data.get("bio") or twitter_data.get("bio", ""),
            "headline": linkedin_data.get("headline", ""),
            "follower_count": {
                **linkedin_data.get("follower_count", {}),
                **twitter_data.get("follower_count", {}),
            },
            "following_count": {
                **linkedin_data.get("following_count", {}),
                **twitter_data.get("following_count", {}),
            },
            "posts": (
                linkedin_data.get("posts", []) + twitter_data.get("posts", [])
            )[:20],
            "topics": list(set(
                linkedin_data.get("topics", []) + twitter_data.get("topics", [])
            )),
            "posting_cadence": {
                **linkedin_data.get("posting_cadence", {}),
                **twitter_data.get("posting_cadence", {}),
            },
        }

        log.info(
            "social_data.merged",
            name=merged["name"],
            posts=len(merged["posts"]),
            linkedin_available=bool(linkedin_data),
            twitter_available=bool(twitter_data),
        )
        return merged

    def get_availability(self) -> dict:
        return {
            "twitter_available": self.twitter.is_available(),
            "linkedin_available": self.linkedin.is_available(),
            "mock_available": True,
        }
