from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator


class ProviderConfig(BaseModel):
    id: str
    name: str
    kind: Literal["ollama", "openai-compatible"] = "ollama"
    base_url: str = "http://localhost:11434"
    api_key: SecretStr | None = None


class AgentConfig(BaseModel):
    id: str
    name: str
    role: str
    model: str = "qwen3:8b"
    provider_id: str = "local"
    instructions: str = ""
    capabilities: list[Literal["list_files", "read_file", "search_files", "write_file"]] = (
        Field(default_factory=lambda: ["list_files", "read_file", "search_files"])
    )
    max_tool_rounds: int = Field(default=6, ge=0, le=20)


class TeamConfig(BaseModel):
    name: str = "My agent team"
    pattern: Literal["pipeline", "panel", "debate", "route"] = "panel"
    agents: list[AgentConfig]
    synthesizer_id: str | None = None
    judge_id: str | None = None
    router_id: str | None = None
    debate_rounds: int = Field(default=2, ge=1, le=8)

    @field_validator("agents")
    @classmethod
    def validate_agents(cls, agents: list[AgentConfig]) -> list[AgentConfig]:
        if not agents:
            raise ValueError("A team requires at least one agent")
        ids = [agent.id for agent in agents]
        if len(ids) != len(set(ids)):
            raise ValueError("Agent IDs must be unique")
        return agents


class RunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20_000)
    team: TeamConfig
    providers: list[ProviderConfig] = Field(default_factory=list)
    workspace: str = "."
    allow_writes: bool = False


class RunResponse(BaseModel):
    output: str
    contributions: dict[str, list[str]]
    events: list[dict[str, object]]


class FilePayload(BaseModel):
    path: str
    content: str

