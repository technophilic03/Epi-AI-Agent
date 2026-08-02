from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import cached_property
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import StructuredTool
from pydantic import ValidationError

from epi_agent.protocol import (
    AgentTool,
    ArtifactRef,
    ToolContext,
    ToolExecutionError,
    ToolResult,
    ToolSpec,
    serialize_tool_result,
)

ToolContextResolver = Callable[[ToolRuntime], ToolContext]


class _RuntimeStructuredTool(StructuredTool):
    """Preserve ToolNode runtime injection outside the model-facing schema."""

    @cached_property
    def _injected_args_keys(self) -> frozenset[str]:
        return frozenset({"runtime"})


class ToolRegistry:
    def __init__(self, tools: Iterable[AgentTool] = ()) -> None:
        self._tools: dict[str, AgentTool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: AgentTool) -> None:
        if tool.spec.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.spec.name}")
        self._tools[tool.spec.name] = tool

    def tools(self) -> tuple[AgentTool, ...]:
        return tuple(self._tools.values())

    def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        context: ToolContext,
    ) -> ToolResult:
        tool = self._require_tool(name)

        try:
            validated = tool.spec.args_model.model_validate(arguments)
        except ValidationError as error:
            raise ToolExecutionError(
                "INVALID_ARGUMENTS",
                f"Invalid arguments for tool {name}: {error}",
                recoverable=True,
            ) from error

        return tool.invoke(validated.model_dump(), context)

    def spec(self, name: str) -> ToolSpec:
        return self._require_tool(name).spec

    def model_schemas(self) -> list[dict[str, Any]]:
        return [tool.spec.model_schema() for tool in self._tools.values()]

    def as_langchain_tools(
        self,
        *,
        context_resolver: ToolContextResolver,
    ) -> list[StructuredTool]:
        return [
            _RuntimeStructuredTool.from_function(
                func=self._langchain_function(tool.spec.name, context_resolver),
                name=tool.spec.name,
                description=tool.spec.description,
                args_schema=tool.spec.args_model,
                response_format="content_and_artifact",
            )
            for tool in self._tools.values()
        ]

    def _langchain_function(
        self,
        name: str,
        context_resolver: ToolContextResolver,
    ):
        def invoke_tool(
            runtime: ToolRuntime,
            **arguments: Any,
        ) -> tuple[str, tuple[ArtifactRef, ...]]:
            context = context_resolver(runtime)
            result = self.invoke(name, arguments, context=context)
            return serialize_tool_result(result), result.artifacts

        return invoke_tool

    def _require_tool(self, name: str) -> AgentTool:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolExecutionError(
                "UNKNOWN_TOOL",
                f"Unknown tool: {name}",
                recoverable=True,
            )
        return tool
