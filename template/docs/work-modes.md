# Work Modes

## Current State

Owner of the phase / runtime split. `tools/phase.py`, `tools/runs.py`, `tools/git_guard.py` (git hooks) and `tools/agent_guard.py` (Claude Code hook) enforce the mechanical parts.

### Classify First

- **Phase**: the user explicitly advances the project: pipeline, capability, structure, rules or docs.
  - Short-video example: improve the editing workflow, add subtitle generation.
- **Runtime**: the user wants routine output from the pipeline as it is. Short-video example: produce one video.
- Ambiguous, or runtime needs a pipeline change: stop and ask. Never turn runtime into phase work silently.

### Phase

1. `python tools/phase.py start <slug>` creates `phase/<N>-<slug>` in a sibling worktree; N is the roadmap `Current Phase`. One phase at a time.
2. Work only in that worktree; commit freely.
3. If the main branch moved, run `git merge <main>` in the worktree and re-verify.
4. Do the [Planning Policy](exec-plans/README.md) handoff, then `python tools/phase.py finish "<summary>"`.
5. `finish` verifies, squash-merges as one commit `phase(<N>): <summary>`, and removes the worktree and branch.

### Runtime

- Records live on the orphan `runs` branch, checked out as the `runs/` worktree (ignored by main).
- Sync: `git pull --ff-only` in the main worktree, `git pull --rebase` in `runs/`.
- Run the pipeline from the main worktree into `runs/<id>/`; large media stays untracked.
- `python tools/runs.py record <id> "<summary>"` stamps `run.json` with the pipeline commit and commits on `runs`. `git push` sends both branches.

### Enforcement

- Main branch: only phase squash commits `phase(<N>): <summary>` (subject at most 72 characters, body at most 5 lines); no merge commits.
- No branch except `runs` may stage `runs/`; pre-push refuses shared history between main and `runs`.
- Hooks are guardrails; for hard enforcement protect the main branch on the server (squash only, linear history).

## Records

