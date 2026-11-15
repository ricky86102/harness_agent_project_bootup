# Model Routing

## Current State

Owner of model tiers, delegation and agent step budgets. `tools/agent_budget.py` (Claude Code hooks) and `.claude/agents/` enforce the mechanical parts. Codex follows this text only.

### Roles

- The session model (recommended: Fable) owns architecture, plans, the roadmap and acceptance. It never delegates them.
- Acceptance: rerun the verification commands and read the diff yourself. A subagent report is a claim, not evidence.
- Subagents never delegate further.

### Tier Rules (first match wins)

1. Architecture, direction, roadmap, phase plan, or acceptance: the session model itself.
2. Read-only work (search code, docs or the web; summarize; locate): `researcher-haiku` or `Explore`.
3. Touches `ARCHITECTURE.md` invariants, `src/core`, schemas, migrations or security; needs a design trade-off; or is hard to undo: `implementer-opus`.
4. Complete spec, acceptance command given, few files (tests to spec, mechanical refactor, template-driven docs): `implementer-sonnet`.
5. Anything else: `implementer-opus`. When unsure, route up, never down.

### Dispatch

- Start every brief with `Tier: <agent> - rule <n>: <reason>`, then the task, files and acceptance command.
- Never override a project tier agent's model. Pass `effort: high` to `implementer-opus` only for rule 3 design trade-offs.
- Escalate: `implementer-sonnet` failing twice goes to `implementer-opus`; an insufficient `researcher-haiku` answer goes to `implementer-sonnet`.

### Built-in Agents

- Only agent types listed in `.claude/agent-budgets.json` may be dispatched; others, including `fork`, are refused.
- A built-in agent pins no model and may inherit the session model, so its call must set `model` from its listed models.
- Tier rules still choose the model: `general-purpose` with `sonnet` follows rule 4, with `opus` rules 3 and 5.
- Built-in agents get the same step budgets and stuck signals as the project tier agents.

### Step Budgets

- Each agent has a tool-call budget in `.claude/agent-budgets.json` and a `maxTurns` backstop in its definition.
- Near the budget the agent is told to wrap up. At the budget every tool call is blocked and the agent must report.
- Stuck signals stop the agent early: an identical tool call repeated, or one file edited too often. Thresholds live in the same JSON file.
- Reports use `Status`, `Tried`, `Evidence`, `Hypothesis`, `Next`; each agent definition holds the format.

### After a Report

- Prefer a fresh agent with the report as its handoff; a fresh context breaks the loop.
- Otherwise narrow the scope into smaller tasks, or take over when the cause is architectural.
- Never extend the budget of the same agent.

## Records

