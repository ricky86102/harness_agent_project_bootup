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

2. **Strategic Roadmap & Active Plan Duality (`docs/exec-plans/`)**:
   - Solves task sprawl, context pollution, and architectural drift by strictly separating long-term product vision from immediate tactical execution:
     - **Single Strategic Truth (`docs/exec-plans/roadmap.md`)**: The only project-wide plan defining goals, ordered phases with status, and approved direction. Only the user approves modifications to it.
     - **Single Active Plan Invariant (`docs/exec-plans/active/`)**: Holds **at most one** active plan corresponding to the current roadmap phase. The plan opens with `Status:`, `Next Step:`, `Blockers:`, and `Roadmap: Phase <N>`, detailing tasks, acceptance criteria (commands and thresholds), and attempt budget.
     - **Atomic Single-Commit Phase Handoff**: Once a phase passes acceptance, verification evidence is recorded, the plan moves to `completed/`, the roadmap phase status is updated, and the next phase is scaffolded in `active/`—all committed together.
     - **Automated Planning Enforcement**: `tools/check_docs.py` mechanically checks for the roadmap, enforces the single active plan limit, verifies the `Roadmap: Phase <N>` binding, and guarantees that the roadmap links to the active plan.
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
   - Rules include: continuous execution, exploration budget (max 3 approaches), pre-registration of intent in the active plan before substantive code changes, hard permission gates (cannot alter the goal, the roadmap, core boundaries, or delete history), and standardized turn heartbeats (`LOOP: attempt <k>/<N> | <state> | <metric>`).

6. **Executable Architectural Boundary Checking (`check_architecture.py`)**:
   - Automatically scans `src/core/` for unauthorized external I/O, UI, OS, or networking dependencies.
   - Ensures pure business logic remains 100% deterministic and decoupled from presentation.

7. **Zero External Dependencies**:
   - Built entirely on Python 3 standard library (`re`, `pathlib`, `hashlib`, `subprocess`, `argparse`, `tempfile`). No `pip install` required.

---

## Repository Files

- **[`bootstrap_harness.py`](bootstrap_harness.py)**: The single-file executable generator that sets up the entire architecture in any new repository.
- **[`update_prompt.txt`](update_prompt.txt)**: A dedicated AI prompt used to reverse-distill newly evolved rules from existing projects back into this toolkit.
- **[`README.md`](README.md)**: Architectural documentation, operational philosophy, and usage instructions.

---

## Generated Directory Blueprint

Running `bootstrap_harness.py` creates the following battle-tested repository structure:

```text
my-project/
├── AGENTS.md                  # Unified AI entrypoint (working rules, planning laws, doc laws, commands)
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
│   ├── README.md              # Document index table (consult on-demand)
│   ├── documentation-policy.md# Two-section structure & rotation rules
│   ├── exec-plans/
│   │   ├── README.md          # Task status board & planning rules overview
│   │   ├── roadmap.md         # Single project-wide strategic plan (phases & approved direction)
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
   - Perform a read-only analysis of your latest rules.
   - De-couple domain business logic from universal architectural patterns.
   - Update `bootstrap_harness.py` and `README.md`.
   - Run end-to-end tests in an isolated sandbox.
   - Commit and push the updates directly back to this repository.

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
