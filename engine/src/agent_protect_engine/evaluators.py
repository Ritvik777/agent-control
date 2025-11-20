"""Rule evaluator implementations."""
import abc
import re
from typing import Any

import re2
from agent_protect_models import EvaluatorResult, RuleEvaluator
from agent_protect_models.rules import ListConfig, RegexConfig


class Evaluator(abc.ABC):
    """Base class for rule evaluators."""

    @abc.abstractmethod
    def evaluate(self, data: Any) -> EvaluatorResult:
        """Evaluate the data against the rule logic."""
        pass


class RegexEvaluator(Evaluator):
    """Evaluator using Regular Expressions (re2)."""

    def __init__(self, config: RegexConfig):
        self.pattern = config.pattern
        self.flags = config.flags

        # re2 python wrapper often has limited flag support compared to 're'
        self._regex = re2.compile(self.pattern)

    def evaluate(self, data: Any) -> EvaluatorResult:
        # Convert data to string for regex matching
        if data is None:
            return EvaluatorResult(matched=False, confidence=1.0, message="No data to match")

        text_data = str(data)

        # re2 search
        match = self._regex.search(text_data)
        is_match = match is not None

        return EvaluatorResult(
            matched=is_match,
            confidence=1.0,  # Regex is deterministic
            message=f"Regex match found: {self.pattern}" if is_match else "No match",
            metadata={"pattern": self.pattern}
        )


class ListEvaluator(Evaluator):
    """Evaluator for checking if values exist in a list."""

    def __init__(self, config: ListConfig):
        self.values = [str(v) for v in config.values]
        self.logic = config.logic
        self.match_on = config.match_on
        self.case_sensitive = config.case_sensitive

        # Compile regex for matching values
        # We use exact match anchors ^...$ because this is a list of discrete values
        if not self.values:
            self._regex = None
        else:
            escaped = [re.escape(v) for v in self.values]
            self.pattern = f"^({'|'.join(escaped)})$"

            if not self.case_sensitive:
                self.pattern = f"(?i){self.pattern}"

            self._regex = re2.compile(self.pattern)

    def evaluate(self, data: Any) -> EvaluatorResult:
        # 1. Normalize input
        if data is None:
            input_values = []
        elif isinstance(data, list):
            input_values = [str(item) for item in data]
        else:
            input_values = [str(data)]

        # 2. Short-circuit if input is empty (Rule Ignored -> Safe)
        if not input_values:
            return EvaluatorResult(
                matched=False,
                confidence=1.0,
                message="Empty input - Rule ignored",
                metadata={"input_count": 0}
            )

        # 3. Short-circuit if rule values are empty (Rule Ignored -> Safe)
        if self._regex is None:
             return EvaluatorResult(
                matched=False,
                confidence=1.0,
                message="Empty rule values - Rule ignored",
                metadata={"input_count": len(input_values)}
            )

        # 4. Perform matching on each item
        matches = []
        for val in input_values:
            if self._regex.search(val):
                matches.append(val)

        match_count = len(matches)
        total_count = len(input_values)

        # 5. Determine if logic condition is met
        condition_met = False
        if self.logic == "any":
            condition_met = match_count > 0
        elif self.logic == "all":
            condition_met = match_count == total_count

        # 6. Apply match_on inversion
        is_match = condition_met
        if self.match_on == "no_match":
            is_match = not condition_met

        # Construct message
        msg_parts = []
        if is_match:
            msg_parts.append("Rule triggered.")
        else:
            msg_parts.append("Rule not triggered.")

        msg_parts.append(f"Logic: {self.logic}, MatchOn: {self.match_on}.")
        if matches:
            msg_parts.append(f"Matched values: {', '.join(matches)}.")
        else:
            msg_parts.append("No values matched.")

        return EvaluatorResult(
            matched=is_match,
            confidence=1.0,
            message=" ".join(msg_parts),
            metadata={
                "logic": self.logic,
                "match_on": self.match_on,
                "matches": matches,
                "input_count": total_count
            }
        )


def get_evaluator(rule_evaluator: RuleEvaluator) -> Evaluator:
    """Factory to create an evaluator instance from configuration."""
    # The RuleEvaluator union (RegexRuleEvaluator | ListRuleEvaluator)
    # automatically types .config correctly for each case if we check type.

    if rule_evaluator.type == "regex":
        # Pydantic guarantees rule_evaluator.config is RegexConfig
        return RegexEvaluator(rule_evaluator.config) # type: ignore

    elif rule_evaluator.type == "list":
        # Pydantic guarantees rule_evaluator.config is ListConfig
        return ListEvaluator(rule_evaluator.config) # type: ignore

    # Fallback/Placeholder
    raise NotImplementedError(f"Evaluator type '{rule_evaluator.type}' not yet implemented")
