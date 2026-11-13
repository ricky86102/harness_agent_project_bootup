# Autonomous Mode

## Current State

Applies to `/goal`, unattended tasks, batch runs, and multi-step goals without continuous human approval.

Read the [Planning Policy](exec-plans/README.md) too. Hard permission gates in [AGENTS](../AGENTS.md) always apply.

1. **Continuous Execution**: Do not halt for routine "what next" questions; keep executing toward the objective.
2. **Exploration Budget**: At most 3 distinct approaches or iterations unless the plan sets another budget. Stop and report if all fail.
3. **Pre-Registration**: Record each approach and its acceptance criteria in the active plan before substantive code changes.
4. **Phase Handoff**: After acceptance, do the Planning Policy handoff and `python tools/phase.py finish`; `start` the next phase if approved.
5. **Turn Heartbeat**: End every turn with `LOOP: attempt <k>/<N> | <current_state> | <verification_metric_or_blocker>`.

## Records

