# Planning Policy

## Current State

Owner of planning rules. `tools/check_docs.py` enforces the mechanical parts.

### Roadmap

- [Roadmap](roadmap.md) is the only project-wide plan: goal, `Current Phase: <N>`, ordered phases with status, approved direction.
- Only the user approves changes to goal, phases or direction. Updating phase status and `Current Phase:` during an approved handoff is routine.

### Active Plan

- `active/` holds at most one plan (subdirectories included), for the roadmap's `Current Phase: <N>`. The roadmap's Phase <N> line links it.
- It opens with `Status:`, `Next Step:`, `Blockers:`, `Roadmap: Phase <N>`.
- Then tasks, acceptance criteria (commands and thresholds) and the attempt budget, detailed enough for unattended `/goal` runs.
- Long specs go in linked design docs; tasks and acceptance stay in the plan.

### Phase Handoff (one squash commit on the main branch)

All steps happen in the phase worktree; see [Work Modes](../work-modes.md).

1. Verify acceptance and record the evidence in the plan.
2. Move the plan to `completed/`.
3. Update the phase status and `Current Phase:` in the roadmap.
4. Write the next phase in full into `active/`, or `Status: awaiting user` with the open decisions if its direction is not approved.
5. Commit, then run `python tools/phase.py finish "<summary>"`. It refuses while the roadmap still names this phase.

### Other Folders

- `completed/`: finished phases with their evidence.
- `paused/`: postponed by the user; never resume without authorization.

## Records

