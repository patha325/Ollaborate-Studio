# Architecture decisions

## Agent runtime

Ollaborate remains the orchestration source of truth. Studio maps visual configurations to `Agent` and `Team`, subscribes to lifecycle events, and returns both final output and individual contributions.

## Provider boundary

Ollama uses its native asynchronous client. External endpoints use a narrow OpenAI-compatible adapter implementing the injectable `chat()` contract expected by Ollaborate. A team using one provider delegates directly to `Team`; mixed-provider teams reproduce the same bounded orchestration semantics while injecting a client per agent.

## Workspace boundary

All file tools receive workspace-relative paths. Paths are resolved before access and rejected when the result is outside the workspace. File writes are excluded from agent tool schemas unless a user enables them for the current run.

## Trust boundary

The model is untrusted. Tool arguments, model output, project content, and remote-provider responses are all untrusted inputs. This prototype does not expose a shell tool. A future terminal executor must require command-level approval and an OS-level sandbox.

