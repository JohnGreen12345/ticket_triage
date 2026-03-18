"""Unit tests for the triage engine — scoring, ranking, determinism."""

from app.engine import get_recommendations, _count_keyword_matches


class TestKeywordMatching:
    def test_counts_single_keyword(self):
        assert _count_keyword_matches("I cannot login", ["login"]) == 1

    def test_counts_multiple_keywords(self):
        assert _count_keyword_matches(
            "password reset login failed", ["password", "reset", "login"]
        ) == 3

    def test_case_insensitive(self):
        assert _count_keyword_matches("PASSWORD Reset", ["password", "reset"]) == 2

    def test_no_matches_returns_zero(self):
        assert _count_keyword_matches("hello world", ["login", "password"]) == 0


class TestGetRecommendations:
    def test_auth_ticket_returns_auth_actions(self):
        recs = get_recommendations(
            title="Cannot log in",
            description="I reset my password but still get an error",
        )
        assert len(recs) == 3
        # Top action should be auth-related
        assert "account" in recs[0].action.lower() or "lockout" in recs[0].action.lower()

    def test_billing_ticket_returns_billing_actions(self):
        recs = get_recommendations(
            title="Double charge on my invoice",
            description="I was charged twice for my subscription this month",
        )
        assert len(recs) == 3
        assert "billing" in recs[0].action.lower() or "transaction" in recs[0].action.lower() or "history" in recs[0].action.lower()

    def test_deterministic_same_input_same_output(self):
        """Core requirement: same input → same ranking every time."""
        args = {
            "title": "Cannot log in",
            "description": "I reset my password but still get an error",
        }
        first = get_recommendations(**args)
        second = get_recommendations(**args)
        assert first == second

    def test_top_n_respected(self):
        recs = get_recommendations(
            title="Cannot log in",
            description="password error",
            top_n=1,
        )
        assert len(recs) == 1

    def test_top_n_max(self):
        recs = get_recommendations(
            title="Cannot log in password reset locked out credential expired",
            description="billing charge invoice subscription slow timeout missing data access denied",
            top_n=10,
        )
        assert len(recs) <= 10

    def test_fallback_when_no_keywords_match(self):
        recs = get_recommendations(
            title="Something unusual",
            description="I have a question about something very vague",
        )
        assert len(recs) == 3
        # Fallback actions should mention gathering steps or knowledge base
        actions_text = " ".join(r.action.lower() for r in recs)
        assert "reproduction" in actions_text or "knowledge base" in actions_text or "escalate" in actions_text

    def test_confidence_descending_within_category(self):
        recs = get_recommendations(
            title="Cannot log in",
            description="password reset error",
        )
        confidences = [r.confidence for r in recs]
        assert confidences == sorted(confidences, reverse=True)

    def test_confidence_between_zero_and_one(self):
        recs = get_recommendations(
            title="password reset locked out",
            description="login credential error sso mfa token session expired",
        )
        for r in recs:
            assert 0.0 <= r.confidence <= 1.0

    def test_empty_after_strip_uses_fallback(self):
        """Edge case: very short input with no keyword matches."""
        recs = get_recommendations(title="Hi", description="Help")
        assert len(recs) == 3
