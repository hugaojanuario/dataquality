from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


CheckStatus = Literal["passed", "failed", "inconclusive", "error", "skipped"]


@dataclass(slots=True)
class CheckResult:
    """Resultado auditável de uma regra de qualidade."""

    name: str
    rule: str
    status: CheckStatus
    issue_count: int
    message: str
    sample: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "passed"


@dataclass(slots=True)
class ValidationReport:
    """Conjunto de resultados produzidos por uma execução."""

    migration_name: str
    started_at: datetime
    results: list[CheckResult] = field(default_factory=list)
    finished_at: datetime | None = None

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(result.passed for result in self.results)

    @property
    def issue_count(self) -> int:
        return sum(result.issue_count for result in self.results)


# @hugaojanuario
