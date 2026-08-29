"""Public entry point for legal assessment."""

from .models import ComplianceResult, ExtractedPackage
from .rules import RuleSet


class ComplianceEngine:
    def __init__(self, rules: RuleSet | None = None) -> None:
        self.rules = rules or RuleSet()

    def evaluate(self, package: ExtractedPackage) -> ComplianceResult:
        return ComplianceResult(outcomes=self.rules.evaluate(package))
