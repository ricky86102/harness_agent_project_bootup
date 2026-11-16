# Codex Policy

## Current State

Owner of Codex role mapping and enforcement. Apply [Model Routing](../model-routing.md).

### Roles and Dispatch

| Shared role | Custom agent | Built-in alternative |
| --- | --- | --- |
| `researcher` | `researcher-terra` | `explorer` |
| `implementer-core` | `implementer-astra` | `worker`, `default` |
| `implementer-spec` | `implementer-sol` | `worker`, `default` |

- Definitions in `.codex/agents/*.toml` pin model and effort; `.codex/agent-budgets.json` owns allowed agents, built-in models and budgets.
- Match each built-in's model and effort to its shared role's custom definition.
- If the host exposes only generic spawning, pass the mapped model, effort and role instructions explicitly with a fresh context.
- If the role or model is unavailable, report the limitation and let the session model take over; never silently inherit another model.
- Custom model/effort values take precedence over spawn values; see [official precedence](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents).

### Budgets and Enforcement

- These limits and read-only role instructions are behavioral; this template installs no Codex tool hook or per-role sandbox.
- Git hooks still enforce commits and pushes. Claude hook payloads cannot be reused as Codex enforcement without an adapter.
- `agents.enabled` is a documented setting; feature-list output alone does not verify dispatch. Confirm tool availability in the target session.

### Skills

- `.agents/skills/doc-review/` exposes the staged-document reviewer through Codex skill discovery.

## Records
