# Architecture decisions

## Agent runtime

Ollaborate remains the orchestration source of truth. Studio maps visual configurations to `Agent` and `Team`, subscribes to lifecycle events, and returns both final output and individual contributions.

## Provider boundary

Ollama uses its native asynchronous client. External endpoints use a narrow OpenAI-compatible adapter implementing the injectable `chat()` contract expected by Ollaborate. A team using one provider delegates directly to `Team`; mixed-provider teams reproduce the same bounded orchestration semantics while injecting a client per agent.

## Workspace boundary

All file tools receive workspace-relative paths. Paths are resolved before access and rejected when the result is outside the workspace. File writes are excluded from agent tool schemas unless a user enables them for the current run.

## MCP plugin boundary

Studio is an MCP host for local stdio servers. It discovers advertised JSON schemas and converts trusted tools into asynchronous Python callables accepted by Ollaborate. Each call uses the official client lifecycle: start the subprocess, initialize a session, call the tool, and close the session.

Plugins are disabled for agents until the server is explicitly marked trusted and explicitly assigned to that agent. The Agent Reach preset is pinned to a reviewed Git commit. Its MCP surface is represented accurately as `get_status`; Studio does not infer tools delegated to upstream CLIs.

## Trust boundary

The model, MCP server, tool arguments, model output, project content, and remote-provider responses are all untrusted inputs. An MCP stdio server executes with the IDE user's OS permissions, so trusting it is equivalent to installing an extension. This prototype does not expose a general shell tool. A future terminal executor must require command-level approval and an OS-level sandbox.
