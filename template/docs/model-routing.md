# Model Routing

## Current State

Owner of shared tier, escalation and budget rules. Resolve roles through the active [host policy](hosts/README.md).

### Roles

- The session model owns architecture, plans, the roadmap and acceptance. It never delegates them.
- Acceptance: rerun the verification commands and read the diff yourself. A subagent report is a claim, not evidence.
- Subagents never delegate further.

### Tier Rules (first match wins)

1. Architecture, direction, roadmap, phase plan, or acceptance: the session model itself.
2. Read-only work (search code, docs or the web; summarize; locate): `researcher`.
3. Touches `ARCHITECTURE.md` invariants, `src/core`, schemas, migrations or security; needs a design trade-off; or is hard to undo: `implementer-core`.
4. Complete spec, acceptance command given, few files (tests to spec, mechanical refactor, template-driven docs): `implementer-spec`.
5. Anything else: `implementer-core`. When unsure, route up, never down.

### Dispatch

- Start every brief with `Tier: <actual-agent> - rule <n>: <reason>`, then the task, files and acceptance command.
- Only dispatch agents in the host's allowlist; keep custom models fixed and explicitly select a listed, tier-matching model for built-ins.
- Escalate `implementer-spec` after two failed attempts to `implementer-core`; escalate insufficient `researcher` findings to `implementer-spec`.

### Step Budgets

- Include the host's JSON tool-call limit and stuck thresholds in the brief; apply them to custom and built-in agents alike.
- Count each tool invocation, including calls inside batches; wrap up at `warn_at`, and report before exceeding the budget.
- Stop on `repeat_limit` identical calls or `same_file_edits` edits to one file.
- At `read_streak`, implement or report the blocker; skip this nudge for read-only roles.
- Follow the role's report format. The host policy states which limits are mechanically enforced.

### After a Report

- Prefer a fresh agent with the report as its handoff; a fresh context breaks the loop.
- Otherwise narrow the scope into smaller tasks, or take over when the cause is architectural.
- Never extend the budget of the same agent.

## Records

