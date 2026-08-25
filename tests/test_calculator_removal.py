from __future__ import annotations

from pathlib import Path

from api.activity_labels import tool_activity_labels
from epi_agent.tool_packs.general.tools import build_general_tool_registry
from tools.mcp_tools import load_servers_config


ROOT = Path(__file__).resolve().parents[1]


def test_general_registry_does_not_expose_calculator() -> None:
    names = {tool.spec.name for tool in build_general_tool_registry().tools()}

    assert "general-calculate" not in names


def test_calculator_mcp_server_and_source_are_removed() -> None:
    servers = load_servers_config()["mcpServers"]

    assert "calculator" not in servers
    assert not (ROOT / "tools" / "calculator_server.py").exists()


def test_historical_calculator_activity_uses_generic_label() -> None:
    labels = tool_activity_labels("general-calculate")

    assert labels.started == "Calculate"
    assert labels.waiting is None
    assert labels.completed == "Calculate"
