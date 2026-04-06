"""
tests/test_services.py — Tests for social data fetcher and metrics tracker.
"""
import pytest
from unittest.mock import patch, MagicMock


# ── Social Data Service Tests ─────────────────────────────────────────────────

class TestTwitterDataFetcher:
    def test_unavailable_returns_mock(self):
        from app.services.social_data import TwitterDataFetcher
        with patch("app.services.social_data.settings") as mock_settings:
            mock_settings.twitter_bearer_token = ""
            fetcher = TwitterDataFetcher()
            result = fetcher.fetch_profile("https://x.com/testuser")
        assert "posts" in result
        assert "name" in result

    def test_extract_username_from_url(self):
        from app.services.social_data import TwitterDataFetcher
        fetcher = TwitterDataFetcher()
        assert fetcher._extract_username("https://x.com/alexchen_ai") == "alexchen_ai"
        assert fetcher._extract_username("https://twitter.com/foo") == "foo"
        assert fetcher._extract_username("@johndoe") == "johndoe"
        assert fetcher._extract_username("johndoe") == "johndoe"

    def test_infer_format_short(self):
        from app.services.social_data import TwitterDataFetcher
        assert TwitterDataFetcher._infer_format("Short tweet.") == "short_post"

    def test_infer_format_thread(self):
        from app.services.social_data import TwitterDataFetcher
        long_text = "x" * 250
        assert TwitterDataFetcher._infer_format(long_text) == "thread"

    def test_mock_fallback_has_required_keys(self):
        from app.services.social_data import TwitterDataFetcher
        data = TwitterDataFetcher._mock_twitter_profile()
        for key in ["name", "bio", "posts", "follower_count", "posting_cadence"]:
            assert key in data

    def test_rate_limit_triggers_fallback(self):
        import httpx
        from app.services.social_data import TwitterDataFetcher
        with patch("app.services.social_data.settings") as mock_settings:
            mock_settings.twitter_bearer_token = "fake_token"
            fetcher = TwitterDataFetcher()
            with patch("httpx.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Rate limit", request=MagicMock(), response=MagicMock(status_code=429)
                )
                mock_get.return_value = mock_resp
                result = fetcher.fetch_profile("testuser")
        assert "posts" in result  # mock fallback


class TestLinkedInDataFetcher:
    def test_unavailable_returns_mock(self):
        from app.services.social_data import LinkedInDataFetcher
        with patch("app.services.social_data.settings") as mock_settings:
            mock_settings.proxycurl_api_key = ""
            fetcher = LinkedInDataFetcher()
            result = fetcher.fetch_profile("https://linkedin.com/in/test")
        assert "posts" in result
        assert "name" in result

    def test_extract_linkedin_url_normalises(self):
        from app.services.social_data import LinkedInDataFetcher
        fetcher = LinkedInDataFetcher()
        url = fetcher._extract_linkedin_url("https://linkedin.com/in/test?utm_source=share")
        assert url == "https://linkedin.com/in/test"

    def test_mock_fallback_structure(self):
        from app.services.social_data import LinkedInDataFetcher
        data = LinkedInDataFetcher._mock_linkedin_profile()
        assert "posts" in data
        assert all(p["platform"] == "linkedin" for p in data["posts"])


class TestSocialDataService:
    def test_use_mock_returns_mock_profile(self):
        from app.services.social_data import SocialDataService
        service = SocialDataService()
        result = service.fetch_combined_profile(use_mock=True)
        assert "name" in result
        assert "posts" in result

    def test_get_availability(self):
        from app.services.social_data import SocialDataService
        service = SocialDataService()
        status = service.get_availability()
        assert "twitter_available" in status
        assert "linkedin_available" in status
        assert status["mock_available"] is True

    @patch("app.services.social_data.TwitterDataFetcher.fetch_profile")
    @patch("app.services.social_data.LinkedInDataFetcher.fetch_profile")
    def test_merge_combines_posts(self, mock_linkedin, mock_twitter):
        from app.services.social_data import SocialDataService
        mock_twitter.return_value = {
            "name": "Twitter Name",
            "bio": "Twitter bio",
            "follower_count": {"twitter": 1000},
            "following_count": {"twitter": 100},
            "posts": [{"platform": "twitter", "text": "tweet 1"}],
            "topics": ["AI"],
            "posting_cadence": {"twitter": "daily"},
        }
        mock_linkedin.return_value = {
            "name": "LinkedIn Name",
            "bio": "LinkedIn bio",
            "follower_count": {"linkedin": 5000},
            "following_count": {"linkedin": 200},
            "posts": [{"platform": "linkedin", "text": "linkedin post 1"}],
            "topics": ["ML"],
            "posting_cadence": {"linkedin": "3x/week"},
        }
        service = SocialDataService()
        result = service.fetch_combined_profile(
            linkedin_url="https://linkedin.com/in/test",
            twitter_url="https://x.com/test",
            use_mock=False,
        )
        assert len(result["posts"]) == 2
        assert result["name"] == "LinkedIn Name"  # LinkedIn preferred
        assert "twitter" in result["follower_count"]
        assert "linkedin" in result["follower_count"]


# ── Metrics Tracker Tests ─────────────────────────────────────────────────────

class TestEngagementScoring:
    def test_score_zero_engagement(self):
        from app.services.metrics_tracker import compute_engagement_score
        assert compute_engagement_score(0, 0, 0) == 0

    def test_score_weighted_correctly(self):
        from app.services.metrics_tracker import compute_engagement_score
        # 10 reactions + 5 comments (×3) + 2 shares (×5) = 10 + 15 + 10 = 35
        assert compute_engagement_score(10, 5, 2) == 35

    def test_shares_weighted_highest(self):
        from app.services.metrics_tracker import compute_engagement_score
        # 1 share should outweigh 4 reactions
        score_shares = compute_engagement_score(0, 0, 1)
        score_reactions = compute_engagement_score(4, 0, 0)
        assert score_shares > score_reactions


class TestPerformanceClassification:
    def test_exceeded_when_score_is_150_percent(self):
        from app.services.metrics_tracker import compute_engagement_score, classify_performance
        # Medium threshold: reactions=100, comments=15, shares=20 → score = 100+45+100 = 245
        # 1.5x = 367.5
        score = compute_engagement_score(200, 30, 50)  # High performer
        result = classify_performance(score, "medium")
        assert result in ("exceeded", "met")

    def test_underperformed_when_score_is_low(self):
        from app.services.metrics_tracker import classify_performance
        result = classify_performance(1, "high")
        assert result == "underperformed"

    def test_met_expectations_in_range(self):
        from app.services.metrics_tracker import compute_engagement_score, classify_performance
        # Medium threshold score
        score = compute_engagement_score(100, 15, 20)
        result = classify_performance(score, "medium")
        assert result in ("met", "exceeded")


class TestAdaptivePlanner:
    def test_no_performance_returns_empty_suggestions(self):
        from app.services.metrics_tracker import AdaptivePlanner
        planner = AdaptivePlanner()
        suggestions = planner.analyse([], [{"day": 1, "topic": "AI", "status": "planned"}])
        assert suggestions == []

    def test_exceeded_generates_amplification_suggestion(self):
        from app.services.metrics_tracker import AdaptivePlanner
        planner = AdaptivePlanner()
        performance = [
            {"topic": "RAG systems", "platform": "linkedin", "score": 500, "performance_class": "exceeded"}
        ]
        remaining = [{"day": 5, "topic": "other topic", "status": "planned"}]
        suggestions = planner.analyse(performance, remaining)
        assert len(suggestions) >= 1
        assert any("RAG systems" in s["reason"] for s in suggestions)

    def test_underperformed_generates_pivot_suggestion(self):
        from app.services.metrics_tracker import AdaptivePlanner
        planner = AdaptivePlanner()
        performance = [
            {"topic": "boring topic", "platform": "twitter", "score": 2, "performance_class": "underperformed"}
        ]
        suggestions = planner.analyse(performance, [])
        assert len(suggestions) >= 1
        assert suggestions[0]["priority"] == "medium"

    def test_format_summary_no_data(self):
        from app.services.metrics_tracker import AdaptivePlanner
        planner = AdaptivePlanner()
        summary = planner.format_summary([])
        assert "No performance data" in summary

    def test_format_summary_with_data(self):
        from app.services.metrics_tracker import AdaptivePlanner
        planner = AdaptivePlanner()
        performance = [
            {"score": 300, "performance_class": "exceeded"},
            {"score": 150, "performance_class": "met"},
            {"score": 10,  "performance_class": "underperformed"},
        ]
        summary = planner.format_summary(performance)
        assert "3 posts tracked" in summary
        assert "1 exceeded" in summary


class TestMetricsService:
    def test_score_and_classify_returns_score(self):
        from app.services.metrics_tracker import MetricsService
        service = MetricsService()
        result = service.score_and_classify(100, 20, 10)
        assert "score" in result
        assert "performance_class" in result
        assert result["score"] == 100 + (20 * 3) + (10 * 5)

    def test_get_adaptive_suggestions_structure(self):
        from app.services.metrics_tracker import MetricsService
        service = MetricsService()
        result = service.get_adaptive_suggestions(
            [{"topic": "AI", "platform": "linkedin", "score": 800, "performance_class": "exceeded"}],
            [{"day": 3, "topic": "other", "status": "planned"}],
        )
        assert "summary" in result
        assert "suggestions" in result
        assert "count" in result

    def test_poll_unknown_platform_returns_none(self):
        from app.services.metrics_tracker import MetricsService
        service = MetricsService()
        result = service.poll_and_record("post_1", "tiktok", "12345")
        assert result is None
