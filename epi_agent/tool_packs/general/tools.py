from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from epi_agent.protocol import (
    ToolContext,
    ToolExecutionError,
    ToolResult,
    ToolSpec,
)
from epi_agent.registry import ToolRegistry
from epi_agent.tool_packs.general.clarification import RequestClarificationTool
from tools.mcp_pool import call_server_tool


class WeatherArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str = Field(min_length=1, max_length=200)
    start_date: str | None = Field(default=None, max_length=10)
    end_date: str | None = Field(default=None, max_length=10)


class WeatherTipsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: Literal["spring", "summer", "autumn", "winter"]


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=1000)
    max_results: int = Field(default=5, ge=1, le=10)


class CalculateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1, max_length=500)


def _serialize_result(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    )


class _GeneralMcpTool:
    spec: ToolSpec
    server: str
    operation: str

    def invoke(
        self,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        del context
        payload = {
            key: value
            for key, value in arguments.items()
            if value is not None
        }
        try:
            result = call_server_tool(
                self.server,
                self.operation,
                **payload,
            )
        except Exception as error:
            raise ToolExecutionError(
                "GENERAL_TOOL_FAILED",
                f"{self.spec.name} failed: {error}",
                recoverable=True,
            ) from error
        return ToolResult(message=_serialize_result(result))


class QueryWeatherTool(_GeneralMcpTool):
    server = "weather"
    operation = "query_weather"
    spec = ToolSpec(
        name="general-query_weather",
        description=(
            "Get current weather or a bounded date-range forecast for a city."
        ),
        args_model=WeatherArgs,
        read_only=True,
        interrupting=False,
    )


class GetWeatherTipsTool(_GeneralMcpTool):
    server = "weather"
    operation = "get_weather_tips"
    spec = ToolSpec(
        name="general-get_weather_tips",
        description="Get concise general advice for a named season.",
        args_model=WeatherTipsArgs,
        read_only=True,
        interrupting=False,
    )


class SearchWebTool(_GeneralMcpTool):
    server = "search"
    operation = "search"
    spec = ToolSpec(
        name="general-search_web",
        description=(
            "Search the public web when current external information is "
            "material to the user's request."
        ),
        args_model=SearchArgs,
        read_only=True,
        interrupting=False,
    )


class CalculateTool(_GeneralMcpTool):
    server = "calculator"
    operation = "calculate"
    spec = ToolSpec(
        name="general-calculate",
        description="Evaluate a bounded arithmetic expression.",
        args_model=CalculateArgs,
        read_only=True,
        interrupting=False,
    )


def build_general_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            RequestClarificationTool(),
            QueryWeatherTool(),
            GetWeatherTipsTool(),
            SearchWebTool(),
            CalculateTool(),
        ]
    )


__all__ = ["build_general_tool_registry"]
