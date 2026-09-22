from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from typing import Any

from .models import MCPServerConfig


class MCPUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class MCPToolInfo:
    server_id: str
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPPluginClient:
    """Short-lived MCP stdio client with explicit server trust boundaries."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config

    @staticmethod
    def _sdk():
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise MCPUnavailableError(
                "MCP support is not installed. Run: pip install 'ollaborate-studio[mcp]'"
            ) from exc
        return ClientSession, StdioServerParameters, stdio_client

    def _parameters(self):
        _, server_parameters, _ = self._sdk()
        env = os.environ.copy()
        env.update({key: value.get_secret_value() for key, value in self.config.env.items()})
        return server_parameters(
            command=self.config.command,
            args=self.config.args,
            env=env,
        )

    async def list_tools(self) -> list[MCPToolInfo]:
        client_session, _, stdio_client = self._sdk()
        async with (
            stdio_client(self._parameters()) as (read, write),
            client_session(read, write) as session,
        ):
            await session.initialize()
            result = await session.list_tools()
        return [
            MCPToolInfo(
                server_id=self.config.id,
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema,
            )
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        client_session, _, stdio_client = self._sdk()
        async with (
            stdio_client(self._parameters()) as (read, write),
            client_session(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(name, arguments=arguments)
        output: list[str] = []
        for block in result.content:
            if hasattr(block, "text"):
                output.append(block.text)
            else:
                output.append(str(block))
        if getattr(result, "isError", False):
            raise RuntimeError("\n".join(output) or f"MCP tool {name} failed")
        return "\n".join(output)

    async def ollaborate_tools(self) -> list[Any]:
        if not self.config.trusted:
            return []
        infos = await self.list_tools()
        return [self._build_tool(info) for info in infos]

    def _build_tool(self, info: MCPToolInfo):
        async def tool(**kwargs: Any) -> str:
            return await self.call_tool(info.name, kwargs)

        tool.__name__ = f"mcp_{self.config.id}_{info.name}".replace("-", "_")
        tool.__doc__ = f"[{self.config.name}] {info.description}".strip()
        properties = info.input_schema.get("properties", {})
        required = set(info.input_schema.get("required", []))
        parameters = []
        for name, schema in properties.items():
            default = inspect.Parameter.empty if name in required else None
            parameters.append(
                inspect.Parameter(
                    name,
                    inspect.Parameter.KEYWORD_ONLY,
                    default=default,
                    annotation=_annotation(schema.get("type")),
                )
            )
        tool.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
        return tool


def _annotation(json_type: str | None):
    return {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }.get(json_type, str)


async def tools_for_agent(
    server_ids: list[str], servers: dict[str, MCPServerConfig]
) -> list[Any]:
    tools: list[Any] = []
    for server_id in server_ids:
        config = servers.get(server_id)
        if config is None:
            raise ValueError(f"Unknown MCP server: {server_id}")
        if config.enabled:
            tools.extend(await MCPPluginClient(config).ollaborate_tools())
    return tools
