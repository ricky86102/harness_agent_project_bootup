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
   - Every document adheres to a normalized two-section format: `# Title` $\rightarrow$ `## Current State` (max 2,000 chars, rewritten in-place) $\rightarrow$ `## Records` (max 5 entries).
   - **Automated Historical Rotation**: When a document accumulates more than 5 logs, `python tools/check_docs.py --fix` automatically rotates older entries into `docs/archive/` while rewriting relative markdown links. The agent's working context stays permanently bounded and immune to token bloat.
   - **AGENTS.md as a Map, Not an Encyclopedia**: Following OpenAI's progressive-disclosure guidance, `AGENTS.md` holds only always-on rules (precedence, hard permission gates, paused-plan authorization, evidence honesty, commit gate), commands, and a **reading-trigger table**. Each detailed rule set has exactly one owning policy, read only when its trigger fires:
     - planning and roadmap work: `docs/exec-plans/README.md` (Planning Policy);
     - editing `docs/`: `docs/documentation-policy.md`;
     - autonomous work: `docs/autonomous-mode.md` plus the Planning Policy.
   - New rules go into their owning policy, so the entrypoint stays small. `check_docs.py` fails if a policy file is missing or `AGENTS.md` does not route to it.

2. **Strategic Roadmap & Active Plan Duality (`docs/exec-plans/`)**:
   - Solves task sprawl, context pollution, and architectural drift by strictly separating long-term product vision from immediate tactical execution:
     - **Single Strategic Truth (`docs/exec-plans/roadmap.md`)**: The only project-wide plan defining goals, ordered phases with status, and approved direction. Its Current State declares the machine-readable marker `Current Phase: <N>`. Only the user approves changes to goal, phases or direction; updating phase status and `Current Phase` during an approved handoff is routine.
     - **Single Active Plan Invariant (`docs/exec-plans/active/`)**: Holds **at most one** active plan (nested subdirectories included) corresponding to the roadmap's `Current Phase`. The plan opens with `Status:`, `Next Step:`, `Blockers:`, and `Roadmap: Phase <N>`, detailing tasks, acceptance criteria (commands and thresholds), and attempt budget.
     - **Atomic Single-Commit Phase Handoff**: Once a phase passes acceptance, verification evidence is recorded, the plan moves to `completed/`, the roadmap phase status and `Current Phase` marker are updated, and the next phase is scaffolded in `active/`—all committed together.
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
   - Automatically scans `src/core/` for unauthorized external I/O, UI, OS, or networking dependencies.
   - Ensures pure business logic remains 100% deterministic and decoupled from presentation.

7. **Zero External Dependencies**:
   - Built entirely on Python 3 standard library (`re`, `pathlib`, `hashlib`, `subprocess`, `argparse`, `tempfile`). No `pip install` required.

---

## Repository Files

- **[`bootstrap_harness.py`](bootstrap_harness.py)**: The single-file executable generator that sets up the entire architecture in any new repository.
- **[`update_prompt.txt`](update_prompt.txt)**: A self-checking AI prompt that reverse-distills newly evolved rules from existing projects back into this toolkit. Its scope derives from the code, not a fixed file list.
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
├── .claude/
│   └── settings.json          # PreToolUse terminal hook for Claude Code
├── .githooks/
│   └── pre-commit             # Git-level boundary & documentation verification
├── tools/
│   ├── check_docs.py          # Enforces doc budget, planning rules & auto-rotates old logs
│   ├── check_architecture.py  # Static AST/Regex checker for Core purity & UI boundaries
│   ├── test_check_docs.py     # Regression tests for documentation guard & planning rules
│   └── verify.py              # Single pipeline command to run all validations
├── docs/
│   ├── README.md              # Navigation-only document index (consult on-demand)
│   ├── documentation-policy.md# Owner: two-section structure, budgets, rotation
│   ├── autonomous-mode.md     # Owner: /goal and unattended execution rules
│   ├── exec-plans/
│   │   ├── README.md          # Owner: Planning Policy (roadmap, active plan, phase handoff)
│   │   ├── roadmap.md         # Single project-wide strategic plan (Current Phase marker, phases, approved direction)
│   │   ├── active/            # At most one active plan (Status / Next Step / Blockers / Roadmap: Phase <N>)
│   │   ├── completed/         # Delivered phases with verification evidence
│   │   └── paused/            # Postponed tasks (do not resume without approval)
│   └── archive/               # Historical records rotated out by check_docs --fix
├── src/
│   ├── core/                  # Pure deterministic logic (no IO/UI/network/OS)
│   └── ui/                    # Container-managed responsive layout
└── tests/
    └── README.md              # Clear partitioning of test responsibilities
```

---

## Quick Start

### 1. Initialize in a New Project

Copy `bootstrap_harness.py` to your new project directory (or call it directly by absolute path):

```bash
mkdir my-new-project
cd my-new-project
git init

# Run the bootstrap script
python bootstrap_harness.py "MyCoolApp"
```

The script will:
1. Scaffold all files and directory trees.
2. Configure `.githooks/pre-commit` as the active Git hooks path (`git config --local core.hooksPath .githooks`).
3. Run initial regression tests and boundary verification to guarantee green-light status.

### 2. Instruct Your AI Agent

You can now immediately instruct Codex, Cursor, Claude, or Copilot:

> *"I have initialized the repository with AGENTS.md and ARCHITECTURE.md. Please read AGENTS.md, review the roadmap in docs/exec-plans/roadmap.md, initialize the active plan in docs/exec-plans/active/ for the current phase, and begin implementation."*

---

## Continuous Evolution: Syncing Architecture Updates

As you develop real-world software, your architectural invariants, boundaries, and verification tools will naturally evolve. To keep this starter kit synchronized without manual editing:

1. Open [`update_prompt.txt`](update_prompt.txt).
2. Copy its contents into an AI session (Cursor, Codex, Claude Code, or Antigravity) inside your evolving project.
3. The AI agent will:
   - Self-check that the prompt still matches the toolkit, and stop with a report if it is stale.
   - Derive its scope from the `FILES` map in `bootstrap_harness.py` instead of a fixed file list, so the scope follows architecture changes.
   - Compare each generated file with your project (read-only), and discover governance files that the toolkit does not cover yet.
   - Trace every mechanically enforced rule to its checker and regression test.
   - Generalize domain logic away, then update `bootstrap_harness.py` and `README.md`.
   - Verify in an isolated sandbox, including a negative test for each synced rule.
   - Report, commit only the changed files, and push after your approval.

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

---

## License

MIT License. Feel free to adopt, modify, and integrate into any personal or enterprise software project.
