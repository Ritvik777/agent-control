"""Tests for rule evaluators."""
import pytest
from agent_protect_models import RuleEvaluator
from agent_protect_models.rules import RegexConfig, ListConfig, RegexRuleEvaluator, ListRuleEvaluator, CustomRuleEvaluator

from agent_protect_engine.evaluators import RegexEvaluator, ListEvaluator, get_evaluator


class TestRegexEvaluator:
    def test_basic_match(self):
        # Given: a regex evaluator configured for SSN pattern
        config = RegexConfig(pattern=r"\d{3}-\d{2}-\d{4}")
        evaluator = RegexEvaluator(config)
        
        # When: evaluating a string containing a valid SSN
        result = evaluator.evaluate("My SSN is 123-45-6789")

        # Then: it should match with high confidence
        assert result.matched is True
        assert result.confidence == 1.0
        assert "123-45-6789" in result.message or "Regex match found" in result.message

    def test_no_match(self):
        # Given: a regex evaluator configured for SSN pattern
        config = RegexConfig(pattern=r"\d{3}-\d{2}-\d{4}")
        evaluator = RegexEvaluator(config)
        
        # When: evaluating a string with no SSN
        result = evaluator.evaluate("No numbers here")

        # Then: it should not match
        assert result.matched is False
        assert result.confidence == 1.0

    def test_non_string_input(self):
        """Test that non-string input is converted to string."""
        # Given: a regex evaluator looking for "123"
        config = RegexConfig(pattern=r"123")
        evaluator = RegexEvaluator(config)
        
        # When: evaluating an integer input 12345
        result = evaluator.evaluate(12345)

        # Then: it should convert to string and match
        assert result.matched is True

    def test_none_input(self):
        """Test handling of None input."""
        # Given: a regex evaluator with a catch-all pattern
        config = RegexConfig(pattern=r".*")
        evaluator = RegexEvaluator(config)
        
        # When: evaluating None input
        result = evaluator.evaluate(None)

        # Then: it should safely return no match
        assert result.matched is False
        assert result.message == "No data to match"

    def test_invalid_regex_pattern(self):
        # Given: an invalid pattern
        # When: initializing the config (validation happens here now, or inside evaluator if we compile)
        # Since we added compilation check in RegexConfig validator, it should raise ValueError there
        with pytest.raises(ValueError):
            RegexConfig(pattern="[")

    def test_empty_pattern_matches_everything(self):
        # Given: a regex evaluator with an empty pattern
        config = RegexConfig(pattern="")
        evaluator = RegexEvaluator(config)
        
        # When: evaluating any string
        result = evaluator.evaluate("something")

        # Then: it should match (empty regex matches everything)
        assert result.matched is True

    def test_get_evaluator_factory(self):
        # Given: a RuleEvaluator configuration for regex type
        config = RegexRuleEvaluator(
            type="regex",
            config=RegexConfig(pattern="abc")
        )

        # When: creating an evaluator via the factory
        evaluator = get_evaluator(config)

        # Then: it should return a correctly configured RegexEvaluator instance
        assert isinstance(evaluator, RegexEvaluator)
        assert evaluator.pattern == "abc"

    def test_get_evaluator_unknown_type(self):
        # Given: a RuleEvaluator configuration for an unsupported type (Custom)
        # Note: CustomRuleEvaluator expects a dict config
        config = CustomRuleEvaluator(
            type="custom",
            config={}
        )

        # When: attempting to create an evaluator
        # Then: it should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            get_evaluator(config)

    def test_list_evaluator_any_match(self):
        # Given: a list evaluator (DenyList equivalent: block if ANY match found)
        config = ListRuleEvaluator(
            type="list",
            config=ListConfig(
                values=["bad", "evil"],
                logic="any",
                match_on="match"
            )
        )
        evaluator = get_evaluator(config)

        # When: evaluating content containing denied terms
        assert evaluator.evaluate("bad").matched is True
        assert evaluator.evaluate("evil").matched is True
        
        # When: evaluating safe content
        assert evaluator.evaluate("good").matched is False
        assert evaluator.evaluate("bad_suffix").matched is False  # Exact match required

    def test_list_evaluator_any_no_match(self):
        # Given: a list evaluator (AllowList equivalent)
        config = ListRuleEvaluator(
            type="list",
            config=ListConfig(
                values=["safe", "ok"],
                logic="any",
                match_on="no_match"
            )
        )
        evaluator = get_evaluator(config)

        # When: evaluating safe values (IN list) -> Rule does NOT trigger (safe)
        assert evaluator.evaluate("safe").matched is False
        assert evaluator.evaluate("ok").matched is False
        
        # When: evaluating unsafe values (NOT in list) -> Rule triggers (match)
        assert evaluator.evaluate("dangerous").matched is True

    def test_list_evaluator_all_match(self):
        # Given: a list evaluator requiring ALL items to match
        config = ListRuleEvaluator(
            type="list",
            config=ListConfig(
                values=["valid1", "valid2"],
                logic="all",
                match_on="match"
            )
        )
        evaluator = get_evaluator(config)

        # When: input list has all valid items
        assert evaluator.evaluate(["valid1", "valid2"]).matched is True
        # When: input list has mixed items
        assert evaluator.evaluate(["valid1", "invalid"]).matched is False
        # When: input list has no items
        assert evaluator.evaluate([]).matched is False

    def test_list_evaluator_case_insensitive(self):
        config = ListRuleEvaluator(
            type="list",
            config=ListConfig(
                values=["MixedCase"],
                case_sensitive=False,
                match_on="match"
            )
        )
        evaluator = get_evaluator(config)
        assert evaluator.evaluate("mixedcase").matched is True
        assert evaluator.evaluate("MIXEDCASE").matched is True
