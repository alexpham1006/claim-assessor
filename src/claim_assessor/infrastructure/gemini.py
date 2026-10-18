import json
from collections.abc import Sequence

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from claim_assessor.assessment.llm import ToolCall, ToolResult, Turn
from claim_assessor.assessment.models import Assessment, Decision, Evidence, ReportDraft
from claim_assessor.assessment.tools import Tool
from claim_assessor.errors import LLMError

TOOL_PROMPT = """You are an insurance claim assessor gathering evidence for one claim.
Call the tools in this order: verifyDocument once for every submitted document,
then lookupPolicy, checkMedicalNecessity, and calculateBenefit.
Copy argument values exactly from the claim. If a tool returns an error, fix the call."""

REPORT_PROMPT = """You write the reasoning section of a claim assessment report.
The recommendation was already decided by deterministic rules; do not change it.
Explain each decision finding in one plain sentence, using only the evidence provided.
Cite only clause ids that exist in the policy, and cite every clause id in the findings.
If validation_errors is not empty, fix every listed problem."""

ANSWER_PROMPT = """Answer the reviewer's question about a claim assessment.
Use only the assessment record provided. If the record does not contain the answer, say so.
Cite policy clause ids when they support the answer."""


class GeminiClient:
    def __init__(
        self, *, api_key: str, model: str, timeout_seconds: float, max_attempts: int
    ) -> None:
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(
                    attempts=max_attempts, initial_delay=5.0, max_delay=60.0
                ),
            ),
        )
        self._model = model

    def next_tool_call(self, conversation: Sequence[Turn], tools: Sequence[Tool]) -> ToolCall:
        declarations = [
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=tool.args_model.model_json_schema(),
            )
            for tool in tools
        ]
        response = self._generate(
            [_to_content(turn) for turn in conversation],
            types.GenerateContentConfig(
                system_instruction=TOOL_PROMPT,
                temperature=0,
                tools=[types.Tool(function_declarations=declarations)],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode=types.FunctionCallingConfigMode.ANY
                    )
                ),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        content = response.candidates[0].content if response.candidates else None
        parts = content.parts if content and content.parts else []
        part = next((part for part in parts if part.function_call), None)
        if part is None or part.function_call is None or not part.function_call.name:
            raise LLMError("Gemini did not return a function call")
        return ToolCall(
            name=part.function_call.name,
            arguments=dict(part.function_call.args or {}),
            replay_token=part.thought_signature,
        )

    def draft_report(
        self, evidence: Evidence, decision: Decision, validation_errors: Sequence[str]
    ) -> ReportDraft:
        prompt = json.dumps(
            {
                "evidence": evidence.model_dump(mode="json"),
                "decision": decision.model_dump(mode="json"),
                "validation_errors": list(validation_errors),
            }
        )
        response = self._generate(
            prompt,
            types.GenerateContentConfig(
                system_instruction=REPORT_PROMPT,
                temperature=0,
                response_mime_type="application/json",
                response_json_schema=ReportDraft.model_json_schema(),
            ),
        )
        try:
            return ReportDraft.model_validate_json(_text(response))
        except ValidationError as error:
            raise LLMError("Gemini returned an invalid report draft") from error

    def answer(self, question: str, assessment: Assessment) -> str:
        prompt = f"Assessment record:\n{assessment.model_dump_json()}\n\nQuestion: {question}"
        response = self._generate(
            prompt, types.GenerateContentConfig(system_instruction=ANSWER_PROMPT, temperature=0)
        )
        return _text(response)

    def _generate(
        self, contents: str | list[types.Content], config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse:
        try:
            return self._client.models.generate_content(
                model=self._model, contents=contents, config=config
            )
        except genai_errors.APIError as error:
            raise LLMError(f"Gemini request failed with status {error.code}") from error
        except httpx.HTTPError as error:
            raise LLMError(f"Gemini request failed: {type(error).__name__}") from error


def _to_content(turn: Turn) -> types.Content:
    match turn:
        case str():
            return types.Content(role="user", parts=[types.Part.from_text(text=turn)])
        case ToolCall():
            call = types.FunctionCall(name=turn.name, args=turn.arguments)
            return types.Content(
                role="model",
                parts=[types.Part(function_call=call, thought_signature=turn.replay_token)],
            )
        case ToolResult():
            return types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=turn.name, response=turn.payload)],
            )


def _text(response: types.GenerateContentResponse) -> str:
    if not response.text:
        raise LLMError("Gemini returned an empty response")
    return response.text
