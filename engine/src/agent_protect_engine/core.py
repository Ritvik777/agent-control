"""Core logic for the protection engine."""
from collections.abc import Sequence
from typing import Protocol

from agent_protect_models import ProtectionRequest, ProtectionResponse, ProtectionRule, RuleMatch

from .evaluators import get_evaluator
from .selectors import select_data


class RuleWithIdentity(Protocol):
    """Protocol for a rule with identity information."""
    id: int
    name: str
    rule: ProtectionRule


class ProtectionEngine:
    """Executes protection rules against requests."""

    def __init__(self, rules: Sequence[RuleWithIdentity]):
        self.rules = rules

    def get_applicable_rules(self, request: ProtectionRequest) -> list[RuleWithIdentity]:
        """
        Get all rules that apply to the current request without evaluating them.
        """
        applicable = []
        payload_is_tool = hasattr(request.payload, "tool_name")

        for item in self.rules:
            rule_def = item.rule

            if not rule_def.enabled:
                continue

            if rule_def.check_stage != request.check_stage:
                continue

            if rule_def.applies_to == "tool_call" and not payload_is_tool:
                continue
            if rule_def.applies_to == "llm_call" and payload_is_tool:
                continue

            applicable.append(item)

        return applicable

    def process(self, request: ProtectionRequest) -> ProtectionResponse:
        """
        Process a protection request against all applicable rules.
        """
        matches: list[RuleMatch] = []
        is_safe = True

        applicable_rules = self.get_applicable_rules(request)

        for item in applicable_rules:
            rule_def = item.rule

            # 2. Select Data
            data = select_data(request.payload, rule_def.selector.path)

            # 3. Evaluate
            evaluator = get_evaluator(rule_def.evaluator)
            result = evaluator.evaluate(data)

            # 4. Act on match
            if result.matched:
                matches.append(RuleMatch(
                    rule_id=item.id,
                    rule_name=item.name,
                    action=rule_def.action.decision,
                    result=result
                ))

                if rule_def.action.decision == "deny":
                    is_safe = False

        return ProtectionResponse(
            is_safe=is_safe,
            confidence=1.0, # Placeholder: simplistic aggregation
            matches=matches if matches else None
        )
