from __future__ import annotations

from api.activity_labels import tool_activity_labels
from epi_agent.tool_packs.general.tools import build_general_tool_registry


def test_general_registry_keeps_live_weather_and_removes_seasonal_tips() -> None:
    names = {tool.spec.name for tool in build_general_tool_registry().tools()}

    assert "general-query_weather" in names
    assert "general-get_weather_tips" not in names


def test_removed_weather_tips_tool_uses_generic_label() -> None:
    labels = tool_activity_labels("general-get_weather_tips")

    assert labels.started == "Get weather tips"
    assert labels.waiting is None
    assert labels.completed == "Get weather tips"
