# Claude Code Policy

## Current State

Owner of Claude role mapping and hook enforcement. Follow [Model Routing](../model-routing.md) for tier selection and escalation.

### Roles

| Shared role | Custom agent | Built-in alternative |
| --- | --- | --- |
| `researcher` | `researcher-haiku` | `Explore`, `claude-code-guide` with `haiku` |
| `implementer-core` | `implementer-opus` | `general-purpose` with `opus` |
| `implementer-spec` | `implementer-sonnet` | `general-purpose` with `sonnet` |

- `.claude/agent-budgets.json` owns allowed types, built-in models and all step thresholds; unlisted types, including `fork`, are refused.
- `.claude/agents/*.md` pins custom models. Opus defaults to `medium`; pass `effort: high` only for rule 3 design trade-offs.
- `Plan` with `sonnet` may gather read-only planning input; the session model still writes and decides plans under shared rule 1.

### Enforcement and Skills

- `tools/agent_budget.py` checks dispatch and counts tools per `agent_id` through `.claude/settings.json` hooks.
- Hooks warn near the budget and block further calls after exhaustion or a stuck signal; custom `maxTurns` values provide a backstop.
- Hook counting does not measure pure reasoning; `effort` controls reasoning intensity.
- `tools/agent_guard.py` checks shell commands for Git workflow bypasses; Git hooks also enforce commits and pushes.
- `.claude/skills/doc-review/` supplies the staged-document review skill.

## Records
