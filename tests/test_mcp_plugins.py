import inspect

import pytest

from ollaborate_studio.mcp_plugins import MCPPluginClient, MCPToolInfo
from ollaborate_studio.models import MCPServerConfig


def config(*, trusted: bool = False) -> MCPServerConfig:
    return MCPServerConfig(
        id="example",
        name="Example",
        command="python",
        args=["-m", "example"],
        trusted=trusted,
    )


def test_agent_reach_preset_is_untrusted_stdio() -> None:
    preset = MCPServerConfig.agent_reach()
    assert preset.command == "python"
    assert preset.args == ["-m", "agent_reach.integrations.mcp_server"]
    assert preset.trusted is False


def test_dynamic_tool_preserves_json_schema_signature() -> None:
    client = MCPPluginClient(config(trusted=True))
    info = MCPToolInfo(
        server_id="example",
        name="search",
        description="Search documents",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["query"],
        },
    )
    tool = client._build_tool(info)
    signature = inspect.signature(tool)

    assert tool.__name__ == "mcp_example_search"
    assert signature.parameters["query"].default is inspect.Parameter.empty
    assert signature.parameters["query"].annotation is str
    assert signature.parameters["limit"].default is None
    assert signature.parameters["limit"].annotation is int


@pytest.mark.asyncio
async def test_untrusted_server_exposes_no_agent_tools(monkeypatch) -> None:
    client = MCPPluginClient(config(trusted=False))

    async def fail_if_called():
        raise AssertionError("Untrusted server must not be contacted for agent tools")

    monkeypatch.setattr(client, "list_tools", fail_if_called)
    assert await client.ollaborate_tools() == []

