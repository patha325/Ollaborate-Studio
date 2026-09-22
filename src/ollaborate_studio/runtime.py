from __future__ import annotations

import asyncio
from typing import Any

from ollaborate import Agent, Team

from .models import AgentConfig, RunRequest, RunResponse
from .providers import make_client
from .workspace import Workspace


async def execute(request: RunRequest) -> RunResponse:
    workspace = Workspace(request.workspace)
    providers = {provider.id: provider for provider in request.providers}
    if "local" not in providers:
        from .models import ProviderConfig

        providers["local"] = ProviderConfig(id="local", name="Local Ollama")

    events: list[dict[str, object]] = []

    def record(event: Any) -> None:
        events.append({"kind": event.kind, "agent": event.agent, "data": event.data})

    configs = {config.id: config for config in request.team.agents}
    agents = {
        config.id: _make_agent(config, workspace, request.allow_writes)
        for config in configs.values()
    }
    provider_ids = {config.provider_id for config in configs.values()}
    if len(provider_ids) != 1:
        result = await _run_mixed_provider_team(request, agents, providers, record)
        return RunResponse(**result, events=events)

    provider_id = next(iter(provider_ids))
    if provider_id not in providers:
        raise ValueError(f"Unknown provider: {provider_id}")
    ordered = [agents[config.id] for config in request.team.agents]
    team = Team(*ordered, client=make_client(providers[provider_id]), on_event=record)
    result = await _dispatch(team, request, agents)
    return RunResponse(output=result.output, contributions=result.contributions, events=events)


def _make_agent(config: AgentConfig, workspace: Workspace, allow_writes: bool) -> Agent:
    available = {
        "list_files": workspace.list_files,
        "read_file": workspace.read_file,
        "search_files": workspace.search_files,
    }
    if allow_writes:
        available["write_file"] = workspace.write_file
    tools = [available[name] for name in config.capabilities if name in available]
    return Agent(
        name=config.name,
        role=config.role,
        model=config.model,
        instructions=config.instructions,
        tools=tools,
        max_tool_rounds=config.max_tool_rounds,
    )


async def _dispatch(team: Team, request: RunRequest, agents: dict[str, Agent]):
    config = request.team
    if config.pattern == "pipeline":
        return await team.pipeline(request.task)
    if config.pattern == "panel":
        synthesizer = agents.get(config.synthesizer_id or "")
        return await team.panel(request.task, synthesizer=synthesizer)
    if config.pattern == "debate":
        judge = agents.get(config.judge_id or "")
        return await team.debate(request.task, rounds=config.debate_rounds, judge=judge)
    router = agents.get(config.router_id or "")
    if router is None:
        raise ValueError("Route pattern requires router_id")
    return await team.route(request.task, router=router)


async def _run_mixed_provider_team(request, agents, providers, record):
    """Preserve Ollaborate patterns when each agent uses a different provider."""
    configs = request.team.agents
    contributions: dict[str, list[str]] = {}

    async def run(config, task, context=None):
        if config.provider_id not in providers:
            raise ValueError(f"Unknown provider: {config.provider_id}")
        answer = await agents[config.id].run(
            task,
            context=context,
            client=make_client(providers[config.provider_id]),
            on_event=record,
        )
        text = str(answer)
        contributions.setdefault(config.name, []).append(text)
        return text

    def transcript():
        return "\n\n".join(
            f"## {name}\n" + "\n\n".join(items)
            for name, items in contributions.items()
            if items
        )

    pattern = request.team.pattern
    if pattern == "pipeline":
        context = None
        for config in configs:
            context = await run(config, request.task, context)
        return {"output": context or "", "contributions": contributions}

    if pattern == "panel":
        synth_id = request.team.synthesizer_id
        members = [config for config in configs if config.id != synth_id]
        answers = await asyncio.gather(*(run(config, request.task) for config in members))
        if not synth_id:
            return {"output": transcript(), "contributions": contributions}
        synth = next(config for config in configs if config.id == synth_id)
        output = await run(
            synth,
            f"Synthesize the strongest answer to the original task: {request.task}",
            "\n\n".join(answers),
        )
        return {"output": output, "contributions": contributions}

    if pattern == "debate":
        judge_id = request.team.judge_id
        debaters = [config for config in configs if config.id != judge_id]
        for round_number in range(1, request.team.debate_rounds + 1):
            await asyncio.gather(
                *(
                    run(
                        config,
                        f"Debate round {round_number}: {request.task}",
                        transcript() or request.task,
                    )
                    for config in debaters
                )
            )
        if not judge_id:
            return {"output": transcript(), "contributions": contributions}
        judge = next(config for config in configs if config.id == judge_id)
        output = await run(judge, f"Judge the debate and answer: {request.task}", transcript())
        return {"output": output, "contributions": contributions}

    router_id = request.team.router_id
    if not router_id:
        raise ValueError("Route pattern requires router_id")
    router = next(config for config in configs if config.id == router_id)
    choices = [config for config in configs if config.id != router_id]
    roster = "\n".join(f"- {config.name}: {config.role}" for config in choices)
    selected_name = (
        await run(
            router,
            "Choose exactly one agent name. Reply only with the name.\n\n"
            f"{roster}\n\nTask: {request.task}",
        )
    ).strip()
    selected = next((config for config in choices if config.name == selected_name), None)
    if not selected:
        raise ValueError(f"Router selected unknown agent: {selected_name!r}")
    output = await run(selected, request.task)
    return {"output": output, "contributions": contributions}
