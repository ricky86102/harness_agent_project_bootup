# Agent Harness Project Bootup

> An automated, zero-dependency, vendor-agnostic bootstrap toolkit that instantly scaffolds a production-grade **Agentic Development Harness** into any software repository.

Supports **OpenAI Codex**, **Claude Code**, **Cursor**, **GitHub Copilot**, **Windsurf**, and **Antigravity**.

---

## Background & Philosophy

This project is inspired by OpenAI's seminal engineering post:  
📖 **[Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)**

In an agent-first software engineering paradigm, the primary bottleneck is rarely model capability; it is the **harness**—the environment, constraints, and feedback loops surrounding the agent. As OpenAI's team discovered while building large-scale software without human-written code:
- Engineering shifts from writing line-by-line syntax to **designing legible environments, enforcing boundaries, and building automated verifiers**.
- Knowledge that is not committed to the repository and mechanically verifiable is effectively invisible to the agent.
- High agent throughput causes catastrophic documentation rot, context pollution, and architectural drift unless strictly governed.

### What We Added: Battle-Tested Practical Innovations

While OpenAI outlined the macro principles of harness engineering, this toolkit operationalizes those concepts into concrete, executable code by blending extensive real-world pair-programming experience:

1. **Mathematical Context Budget & Anti-Rot Engine (`check_docs.py`)**:
   - Instead of letting documentation grow indefinitely, we impose strict mathematical character budgets (e.g., `AGENTS.md` $\le$ 4,000 chars, `ARCHITECTURE.md` $\le$ 6,000 chars, total must-read budget $\le$ 10,000 chars).
   - Every document adheres to a normalized two-section format: `# Title` $\rightarrow$ `## Current State` (rewritten in place; max 3,000 chars for owning policies, 2,000 for other docs) $\rightarrow$ `## Records` (max 5 entries).
   - **Terse Writing Rules**: `AGENTS.md` carries an always-on rule; `docs/documentation-policy.md` owns the details. `check_docs.py` rejects:
     - lines over 200 characters (one fact per line; fenced code exempt);
     - filler phrases from its `FILLER` list, such as "please note" or "in order to" (inline code exempt);
     - any normalized line of 80+ characters repeated in a second document (state a rule once, link elsewhere).
   - Verbosity is blocked where it starts, so budgets rarely force a later rewrite. Rules a checker cannot judge (imperative voice, edit in place, no appended notes) stay in the policy as text.
   - **Automated Historical Rotation**: When a document accumulates more than 5 logs, `python tools/check_docs.py --fix` automatically rotates older entries into `docs/archive/` while rewriting relative markdown links. The agent's working context stays permanently bounded and immune to token bloat.
   - **AGENTS.md as a Map, Not an Encyclopedia**: Following OpenAI's progressive-disclosure guidance, `AGENTS.md` holds only always-on rules (precedence, hard permission gates, paused-plan authorization, evidence honesty, commit gate), commands, and a **reading-trigger table**. Each detailed rule set has exactly one owning policy, read only when its trigger fires:
     - planning and roadmap work: `docs/exec-plans/README.md` (Planning Policy);
     - editing `docs/`: `docs/documentation-policy.md`;
     - autonomous work: `docs/autonomous-mode.md` plus the Planning Policy;
     - any request that changes files (phase or runtime): `docs/work-modes.md`.
   - New rules go into their owning policy, so the entrypoint stays small. `check_docs.py` fails if a policy file is missing or `AGENTS.md` does not route to it.

2. **Strategic Roadmap & Active Plan Duality (`docs/exec-plans/`)**:
   - Solves task sprawl, context pollution, and architectural drift by strictly separating long-term product vision from immediate tactical execution:
     - **Single Strategic Truth (`docs/exec-plans/roadmap.md`)**: The only project-wide plan defining goals, ordered phases with status, and approved direction. Its Current State declares the machine-readable marker `Current Phase: <N>`. Only the user approves changes to goal, phases or direction; updating phase status and `Current Phase` during an approved handoff is routine.
     - **Single Active Plan Invariant (`docs/exec-plans/active/`)**: Holds **at most one** active plan (nested subdirectories included) corresponding to the roadmap's `Current Phase`. The plan opens with `Status:`, `Next Step:`, `Blockers:`, and `Roadmap: Phase <N>`, detailing tasks, acceptance criteria (commands and thresholds), and attempt budget.
     - **Single Squash-Commit Phase Handoff**: Once a phase passes acceptance, verification evidence is recorded, the plan moves to `completed/`, the roadmap phase status and `Current Phase` marker are updated, and the next phase is scaffolded in `active/`. `tools/phase.py finish` then lands the whole phase on the main branch as one commit (see item 8).
     - **Automated Planning Enforcement**: `tools/check_docs.py` mechanically checks for the roadmap and enforces the single active plan limit. It reads only the `## Current State` sections, so stale `## Records` history cannot satisfy a check, and it fails closed when a document is malformed. It verifies that:
       - the plan's opening lines declare `Roadmap: Phase <N>`;
       - `<N>` equals the roadmap's `Current Phase: <N>`, so a completed phase cannot hold the active plan;
       - the roadmap's Phase `<N>` line links to the active plan.
     - **Initialization Exit Status**: `bootstrap_harness.py` exits non-zero when the initial verification fails, so scripted setups detect a broken scaffold.
     - **Clear Precedence Hierarchy**: Explicit User Instruction > Roadmap > Active Plan.

3. **Git Index-Level Mechanical Enforcement (`--staged` Pre-Commit Guard)**:
   - Rules in text are frequently ignored by LLMs; automated gates are not.
   - The `.githooks/pre-commit` hook does not merely inspect the dirty working tree; it inspects Git index blobs directly (`git cat-file --batch`), preventing agents from bypassing checks with unstaged fixes.

4. **Universal Multi-Agent Alignment (Vendor-Agnostic Single Source of Truth)**:
   - `AGENTS.md` is the universal core configuration.
   - Thin pointers ensure compatibility across all leading agent platforms:
     - **OpenAI Codex / Generic Agent**: Native reading of `AGENTS.md`.
     - **Cursor IDE**: `.cursorrules` pointing to `AGENTS.md`.
     - **GitHub Copilot**: `.github/copilot-instructions.md` pointing to `AGENTS.md`.
     - **Claude Code**: `CLAUDE.md` (`@AGENTS.md`) + `.claude/settings.json` PreToolUse hook.
     - **Antigravity / Gemini**: Direct ingestion of `AGENTS.md`.

5. **Autonomous Mode & `/goal` Guardrails**:
   - Solves the common failure modes of long-running, unattended agent loops (premature halting, infinite loops, moving goalposts, or destructive mutations).
   - Rules in `docs/autonomous-mode.md` include: continuous execution, exploration budget (max 3 approaches), pre-registration of intent in the active plan before substantive code changes, phase handoff, and standardized turn heartbeats (`LOOP: attempt <k>/<N> | <state> | <metric>`).
   - Hard permission gates stay in `AGENTS.md` so they are always visible: no changes to the roadmap goal, phases or direction, no weakened acceptance criteria, no changes to core invariants, no deleted evidence, no exceeded iteration budget.

6. **Executable Architectural Boundary Checking (`check_architecture.py`)**:
   - Scans `src/core/` for I/O, OS, process, network, persistence or UI dependencies, and `src/ui/` for hardcoded screen positions.
   - Python is checked through its AST (imports and calls such as `open()`); JS/TS, Vue, Svelte, Go, Rust, GDScript and CSS through a comment- and string-aware scanner. Prose in comments or strings that mentions `http.` or `window.` does not fail the build, while `obj.window` property access is not mistaken for the global.
   - Reports `path:line: message`, fails closed on unparsable Python, and is covered by `tools/test_check_architecture.py`. Documentation checks run separately, so the pre-commit hook no longer checks docs twice.

7. **Zero External Dependencies**:
   - Built entirely on Python 3 standard library (`re`, `ast`, `pathlib`, `hashlib`, `subprocess`, `argparse`, `tempfile`). No `pip install` required.

8. **Phase vs Runtime Work Modes (`docs/work-modes.md`)**:
   - Every request is classified first. **Phase**: the user explicitly advances the project (for a short-video project: improve the editing workflow, add subtitle generation). **Runtime**: the user wants routine output from the current pipeline (produce one video). Ambiguous requests are asked about, never silently promoted.
   - **Phase work runs in its own git worktree.** `python tools/phase.py start <slug>` creates `phase/<N>-<slug>` in a sibling directory (`<repo>.worktrees/`), where N is the roadmap `Current Phase`; one phase at a time. Commits there are free-form.
   - `python tools/phase.py finish "<summary>"` refuses unless the phase worktree is clean, the main branch has not moved (otherwise merge it into the phase first), and the roadmap handoff is done. It then runs `tools/verify.py` in the worktree, squash-merges, commits `phase(<N>): <summary>`, and removes the worktree and branch. The main branch history stays one commit per phase.
   - **Runtime records live on an orphan `runs` branch**, checked out as the `runs/` worktree inside the main worktree (the main branch ignores `runs/`). The two branches share no history, so main-branch updates never require a rebase of `runs`, and daily records never touch the main history.
     - `python tools/runs.py setup` (run by bootstrap, and on every fresh clone) is idempotent: it points `core.hooksPath` at the main worktree's absolute `.githooks/` so the hooks also run in phase and runs worktrees, records `harness.mainBranch`, creates the orphan `runs` branch (seeded with a media-ignoring `.gitignore`) or tracks `origin/runs`, adds the `runs/` worktree, and adds `remote.origin.push` refspecs so one `git push` sends both branches.
     - `python tools/runs.py record <id> "<summary>"` stamps `runs/<id>/run.json` with the pipeline commit (`pipeline`, `pipeline_dirty`, `recorded_at`) while keeping fields the pipeline wrote, then commits `run(<id>): <summary>` on `runs`. `status` shows uncommitted and unpushed records.
     - Daily flow: `git pull --ff-only` in the main worktree and `git pull --rebase` in `runs/`; run the pipeline into `runs/<id>/`; `record`; `git push`.
   - **Enforcement** (`tools/git_guard.py`, wired as git hooks):
     - `pre-commit`: the main branch accepts only a phase squash merge in progress (or the first commit), then runs docs and architecture checks; no branch except `runs` may stage `runs/`; phase and runs branches commit freely.
     - `commit-msg`: main-branch subject `phase(<N>): <summary>` at most 72 characters, body at most 5 lines (trailers allowed), so git's verbose default squash message is rejected.
     - `pre-merge-commit`: no merge commits on the main branch.
     - `pre-push`: catches what local hooks cannot see, such as a fast-forward merge of a phase branch: merge commits and non-phase commits pushed to the main branch are refused, and so is any shared history between the main and `runs` branches. History before bootstrap (`harness.baseline`) is exempt.
     - `tools/agent_guard.py` (Claude Code PreToolUse hook) blocks `--no-verify`, `git commit -n`, `core.hooksPath` changes, `update-ref`, force pushes, `--allow-unrelated-histories`, double-force `git clean`, switching branches inside the `runs/` worktree, and non-squash `git merge` on the main branch.
   - **Limits**: local hooks are guardrails, not security; anyone with shell access can still bypass them. For hard enforcement, protect the main branch on the server (squash merge only, linear history, required checks).

---

9. **LLM Document Review (`tools/doc_review.py`, run by pre-commit)**:
   - A small model judges only the cleanliness of staged changes to `AGENTS.md`, `ARCHITECTURE.md` and `docs/` (archive excluded). Commits without document changes cost nothing.
   - **Engines**: Claude Haiku (`claude -p`) or Codex `gpt-6-luna` (`codex exec`). `git config harness.reviewer claude|codex` forces one; otherwise the committing agent is detected (`CLAUDECODE` / `CODEX_*`), then the first CLI found. Models: `harness.reviewerClaudeModel`, `harness.reviewerCodexModel`.
   - **Scope is enforced, not requested**: the hook builds the diff from `check_docs.is_document()` paths only and pipes it on stdin. The CLI runs in an empty temporary directory with no tools (Claude) or a read-only sandbox (Codex), without user or project settings. Replies naming any other file are rejected.
   - **Nothing goes stale**: the prompt file holds only the frame. The rubric is the Current State of `docs/documentation-policy.md` at HEAD, so editing the policy edits the reviewer, and a commit cannot loosen the rules it is judged by. Owners come from the `AGENTS.md` trigger table and `check_docs.POLICIES`. A regression test fails if policy rules are copied into the frame.
   - **Output**: one JSON object (`verdict`, `issues[file,line,problem,fix]`); `fail` or an unusable reply blocks the commit. Diffs over 30,000 characters must be split.
   - **Cost control**: approved document contents are cached by blob in the shared git directory, so a phase squash merge does not re-review content already approved in its worktree. The first scaffold commit is not reviewed.
   - **Outages** (CLI missing, logged out, timeout) warn and allow the commit; `git config harness.reviewStrict true` blocks instead. `tools/agent_guard.py` blocks agents from changing `harness.review*` settings.
   - The deterministic `check_docs.py` rules stay the primary gate; the model only judges what they cannot (vague, misplaced, stale or appended text). Prompt injection inside a diff is mitigated (data fences, no tools, JSON-only reply), not eliminated.

10. **Model Routing and Step Budgets (`docs/model-routing.md`)**:
    - The session model (recommended: Claude Fable) owns architecture, plans and acceptance, and never delegates them. Acceptance means rerunning verification and reading the diff; a subagent report is a claim.
    - **Tier rules, first match wins**: read-only search goes to `researcher-haiku`; core, invariants, schemas, migrations, security, design trade-offs or hard-to-undo work goes to `implementer-opus`; fully specified work with an acceptance command goes to `implementer-sonnet`; anything else goes to Opus. When unsure, route up.
    - **The model is fixed by the agent definition** (`.claude/agents/*.md`: `model`, `effort`, `maxTurns`, and for Haiku a read-only `tools` list). `tools/agent_budget.py` blocks a `model` override on these agents and briefs that do not start with `Tier: <agent> - rule <n>: <reason>`.
    - **Built-in agents** (`Explore`, `Plan`, `claude-code-guide`, `general-purpose`) are allowed only as listed in `.claude/agent-budgets.json`. They pin no model and may inherit the expensive session model, so each call must set `model` from the agent's list (for example `Explore` with `haiku`, `general-purpose` with `sonnet` or `opus`). Unlisted types, including `fork`, are refused. They get the same budgets and stuck signals.
    - **Step budgets against thinking loops**: every subagent tool call is counted per `agent_id` against `.claude/agent-budgets.json`. Near the budget the agent is told to wrap up; at the budget, or on a stuck signal (identical call repeated, one file edited too often), every further call is blocked and the agent must reply with `Status / Tried / Evidence / Hypothesis / Next`. Long read-only streaks in implementers trigger a nudge. `maxTurns` is the backstop; `effort` caps pure reasoning, which hooks cannot see.
    - **After a report**, the session model starts a fresh agent with the report as handoff, narrows the scope, or takes over; it never extends the same agent's budget. Subagents cannot delegate further.
    - Thresholds live only in the JSON file; a regression test fails if the policy hard-codes them. Codex has no equivalent hooks and follows the policy text only.

---

## Repository Files

- **[`bootstrap_harness.py`](bootstrap_harness.py)**: The generator. It copies `template/` into the current directory, sets up git, and runs the initial verification.
- **[`template/`](template/)**: Every generated file, maintained as ordinary files at its generated path. Edit, lint and test them directly.
  - A trailing `.tmpl` is stripped on generation (`AGENTS.md.tmpl`, `CLAUDE.md.tmpl`, `.gitignore.tmpl`), so these files do not act on this toolkit repository itself.
  - Test the templates in place: `python -m unittest discover -s template/tools -p "test_*.py"`.
- **[`README.md`](README.md)**: Architectural documentation, operational philosophy, and usage instructions.

---

## Generated Directory Blueprint

Running `bootstrap_harness.py` creates the following battle-tested repository structure:

```text
my-project/
├── AGENTS.md                  # Unified AI entrypoint: a map (always-on rules, reading triggers, commands)
├── ARCHITECTURE.md            # Dependency direction, ownership model, invariants
├── CLAUDE.md                  # Points to @AGENTS.md
├── .cursorrules               # Points to AGENTS.md for Cursor / Codex
├── .github/
│   └── copilot-instructions.md# Points to AGENTS.md for Copilot / Codex
├── .gitignore                 # Ignores /runs/ (the runs branch worktree)
├── .claude/
│   ├── settings.json          # Claude Code hooks: agent_guard (shell), agent_budget (every tool)
│   ├── agent-budgets.json     # Tool-call budgets and stuck-signal thresholds per tier agent
│   ├── agents/                # implementer-opus, implementer-sonnet, researcher-haiku
│   └── skills/doc-review/     # Skill: run the document review before committing
├── .githooks/
│   ├── pre-commit             # Main branch: phase squash only; docs & architecture checks; LLM document review
│   ├── commit-msg             # Main branch: concise "phase(<N>): ..." messages
│   ├── pre-merge-commit       # Main branch: no merge commits
│   └── pre-push               # Main branch: refuse merge / non-conforming commits
├── tools/
│   ├── check_docs.py          # Enforces doc budget, planning rules & auto-rotates old logs
│   ├── check_architecture.py  # AST / comment-aware checker for Core purity & UI boundaries
│   ├── git_guard.py           # Git hook logic for the phase / runtime workflow
│   ├── phase.py               # start / status / finish a phase worktree (squash merge)
│   ├── runs.py                # setup / record / status for the orphan runs branch worktree
│   ├── agent_guard.py         # Claude Code guard against hook bypass and non-squash merges
│   ├── doc_review.py          # LLM cleanliness review of staged document diffs (pre-commit)
│   ├── agent_budget.py        # Dispatch checks and subagent step budgets (Claude Code hooks)
│   ├── doc_review_prompt.md   # Reviewer frame only: role, data boundaries, JSON reply shape
│   ├── test_check_docs.py     # Regression tests for documentation guard & planning rules
│   ├── test_check_architecture.py # Regression tests for the architecture checker
│   ├── test_git_guard.py      # Regression tests for the workflow guards
│   ├── test_doc_review.py     # Regression tests for the document reviewer (fake CLI)
│   ├── test_agent_budget.py   # Regression tests for model routing and step budgets
│   └── verify.py              # Single pipeline command to run all validations
├── docs/
│   ├── README.md              # Navigation-only document index (consult on-demand)
│   ├── documentation-policy.md# Owner: two-section structure, budgets, rotation
│   ├── autonomous-mode.md     # Owner: /goal and unattended execution rules
│   ├── work-modes.md          # Owner: phase vs runtime, worktree and squash-merge rules
│   ├── model-routing.md       # Owner: model tiers, delegation, step budgets, reports
│   ├── exec-plans/
│   │   ├── README.md          # Owner: Planning Policy (roadmap, active plan, phase handoff)
│   │   ├── roadmap.md         # Single project-wide strategic plan (Current Phase marker, phases, approved direction)
│   │   ├── active/            # At most one active plan (Status / Next Step / Blockers / Roadmap: Phase <N>)
│   │   ├── completed/         # Delivered phases with verification evidence
│   │   └── paused/            # Postponed tasks (do not resume without approval)
│   └── archive/               # Historical records rotated out by check_docs --fix
├── runs/                      # Worktree of the orphan runs branch (runtime records; ignored by main)
├── src/
│   ├── core/                  # Pure deterministic logic (no IO/UI/network/OS)
│   └── ui/                    # Container-managed responsive layout
└── tests/
    └── README.md              # Clear partitioning of test responsibilities
```

---

## Quick Start

### 1. Initialize in a New Project

Call `bootstrap_harness.py` by its path in the toolkit checkout; it reads `template/` next to itself:

```bash
mkdir my-new-project
cd my-new-project
git init

# Run the bootstrap script from the toolkit checkout
python /path/to/harness_agent_project_bootup/bootstrap_harness.py "MyCoolApp"
```

The script will:
1. Scaffold all files and directory trees.
2. In a repository with history, record `harness.baseline` so older commits are exempt from the pre-push rules, then run `python tools/runs.py setup`: absolute hooks path, protected main branch (`harness.mainBranch`, the current branch), orphan `runs` branch and `runs/` worktree, and push refspecs once `origin` exists.
3. Run initial regression tests and boundary verification to guarantee green-light status.

Commit the scaffold on the main branch (the first commit is exempt from the phase-only rule), then start the first phase with `python tools/phase.py start <slug>`. After adding a remote, rerun `python tools/runs.py setup` and push with `git push -u origin <main> runs`. On a fresh clone, run `python tools/runs.py setup` once.

### 2. Instruct Your AI Agent

You can now immediately instruct Codex, Cursor, Claude, or Copilot:

> *"I have initialized the repository with AGENTS.md and ARCHITECTURE.md. Please read AGENTS.md, review the roadmap in docs/exec-plans/roadmap.md, initialize the active plan in docs/exec-plans/active/ for the current phase, and begin implementation."*

---

## Daily Verification Commands

- **Run all checks**:
  ```bash
  python tools/verify.py
  ```
- **Check architectural boundaries**:
  ```bash
  python tools/check_architecture.py
  ```
- **Check documentation budget & planning invariants**:
  ```bash
  python tools/check_docs.py
  ```
- **Auto-rotate documentation history when logs exceed 5 entries**:
  ```bash
  python tools/check_docs.py --fix
  ```
- **Runtime records**:
  ```bash
  python tools/runs.py setup
  python tools/runs.py record 0047_the-raven "accept episode"
  python tools/runs.py status
  ```
- **Phase workflow**:
  ```bash
  python tools/phase.py start subtitle-pipeline
  python tools/phase.py status
  python tools/phase.py finish "add subtitle pipeline"
  ```

---

## License

MIT License. Feel free to adopt, modify, and integrate into any personal or enterprise software project.
