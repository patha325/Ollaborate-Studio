from __future__ import annotations

import inspect
import os
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
from ollama import AsyncClient

from .models import ProviderConfig


def make_client(config: ProviderConfig) -> object:
    if config.kind == "ollama":
        return AsyncClient(host=config.base_url)
    key = config.api_key.get_secret_value() if config.api_key else None
    return OpenAICompatibleClient(config.base_url, key)


class OpenAICompatibleClient:
    """Small adapter from Ollaborate's injectable client contract to Chat Completions."""

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[Callable[..., Any]] | None = None,
        format: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> SimpleNamespace:
        headers = {"Content-Type": "application/json"}
        api_key = self.api_key or os.getenv("OPENAI_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload: dict[str, Any] = {"model": model, "messages": self._messages(messages)}
        if tools:
            payload["tools"] = [self._tool_schema(tool) for tool in tools]
        if format:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "ollaborate_output", "schema": format},
            }
        payload.update(options or {})
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]
        calls = []
        for call in raw.get("tool_calls") or []:
            import json

            fn = call["function"]
            calls.append(
                SimpleNamespace(
                    function=SimpleNamespace(
                        name=fn["name"], arguments=json.loads(fn.get("arguments") or "{}")
                    )
                )
            )
        message = SimpleNamespace(
            content=raw.get("content") or "",
            tool_calls=calls,
            model_dump=lambda exclude_none=True: raw,
        )
        return SimpleNamespace(message=message)

    @staticmethod
    def _messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted = []
        pending_call_ids: dict[str, list[str]] = {}
        for message in messages:
            item = dict(message)
            for call in item.get("tool_calls") or []:
                function = call.get("function", {})
                if call.get("id") and function.get("name"):
                    pending_call_ids.setdefault(function["name"], []).append(call["id"])
            if item.get("role") == "tool" and "tool_name" in item:
                name = item.pop("tool_name")
                item["name"] = name
                ids = pending_call_ids.get(name, [])
                if ids:
                    item["tool_call_id"] = ids.pop(0)
            converted.append(item)
        return converted

    @staticmethod
    def _tool_schema(tool: Callable[..., Any]) -> dict[str, Any]:
        signature = inspect.signature(tool)
        properties: dict[str, Any] = {}
        required: list[str] = []
        type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}
        for name, parameter in signature.parameters.items():
            properties[name] = {"type": type_map.get(parameter.annotation, "string")}
            if parameter.default is inspect.Parameter.empty:
                required.append(name)
        return {
            "type": "function",
            "function": {
                "name": tool.__name__,
                "description": inspect.getdoc(tool) or "",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
