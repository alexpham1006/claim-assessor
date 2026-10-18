from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from claim_assessor.assessment.models import Assessment, Decision, Evidence, ReportDraft
from claim_assessor.assessment.tools import Tool


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: dict[str, object]
    # Opaque provider data; must be sent back with this call or the provider rejects the turn.
    replay_token: bytes | None = None


@dataclass(frozen=True, slots=True)
class ToolResult:
    name: str
    payload: dict[str, object]


Turn = str | ToolCall | ToolResult


class LLMClient(Protocol):
    def next_tool_call(self, conversation: Sequence[Turn], tools: Sequence[Tool]) -> ToolCall: ...

    def draft_report(
        self, evidence: Evidence, decision: Decision, validation_errors: Sequence[str]
    ) -> ReportDraft: ...

    def answer(self, question: str, assessment: Assessment) -> str: ...
