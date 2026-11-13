"""
bootstrap_harness.py
Universal, vendor-agnostic bootstrap script for the "Agentic Harness" development architecture.
Supports Claude Code, OpenAI Codex, Cursor, GitHub Copilot, Windsurf, and Antigravity.

Usage: python bootstrap_harness.py [ProjectName]
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

# Windows console encoding compatibility
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

FILES = {
    "AGENTS.md": """# Project Entrypoint

## Required Reading

Always read this file, [Architecture](ARCHITECTURE.md), and the active plan in `docs/exec-plans/active/`. Load other documents only through these triggers; NEVER load documents in bulk.

| Before you | Read |
| --- | --- |
| act on any request that changes files: classify it as phase or runtime, start or finish a phase, produce runtime output | [Work Modes](docs/work-modes.md) |
| create, change or hand off a plan, or touch the roadmap | [Planning Policy](docs/exec-plans/README.md) |
| create or edit `AGENTS.md`, `ARCHITECTURE.md` or a document under `docs/` | [Documentation Policy](docs/documentation-policy.md) |
| start autonomous work (`/goal`, unattended or batch runs) | [Autonomous Mode](docs/autonomous-mode.md) and [Planning Policy](docs/exec-plans/README.md) |
| look for anything else | [Index](docs/README.md) |

## Working Rules

- Use English for user communication, code, commands, and documentation.
- The user decides product direction; ask when uncertain instead of assuming competitor behavior or making guesses. Confirmed instructions override historical records.
- Strict architectural boundaries: `src/core` is pure business logic and must NOT depend on platform APIs, UI, networking, or external I/O.
- UI uses responsive layout containers; NEVER hardcode screen positions or offsets.
- Presentation only projects state snapshots; animation and rendering must NOT trigger state side-effects.
- Decisions, constraints, and evidence are preserved in the repository. Unverified features must never be marked as completed.

## Always-On Rules

- Precedence: explicit user instruction > [Roadmap](docs/exec-plans/roadmap.md) > active plan. If the plan and the roadmap disagree, stop and ask.
- Classify every request first; if unclear, ask.
  - **Phase**: the user explicitly advances the project (improve the pipeline, add a capability).
  - **Runtime**: the user wants routine output from the current pipeline.
  - Phase work happens only in a `phase/*` worktree (`python tools/phase.py start <slug>`) and reaches the main branch only through `python tools/phase.py finish "<summary>"`.
  - Runtime work writes only into `runs/<id>/` (the `runs` branch worktree) and commits with `python tools/runs.py record`.
  - Runtime work never changes code, tools, docs or plans.
- Write documents tersely: one fact per line, no filler, each rule once in its owner, edits in place. `check_docs.py` rejects violations.
- Never resume a plan in `docs/exec-plans/paused/` without authorization.
- Hard permission gates for autonomous work. Halt and ask the user before:
  - changing the roadmap goal, phases or approved direction (an approved phase handoff may update phase status and `Current Phase:`);
  - weakening acceptance criteria or test assertions;
  - modifying core invariants, schemas or dependency rules in `ARCHITECTURE.md`;
  - deleting test logs, metrics or archival evidence;
  - exceeding the iteration budget.
- Never bypass the git hooks (`--no-verify`, changing `core.hooksPath`, `update-ref`, force push). Never merge between the main and `runs` branches.
- `python tools/check_docs.py` must pass before commit; the pre-commit hook checks the staged index. Run `python tools/runs.py setup` on every fresh clone.

## Commands

- Full verification: `python tools/verify.py`
- Phase: `python tools/phase.py start <slug>` / `status` / `finish "<summary>"`
- Runtime: `python tools/runs.py record <id> "<summary>"` / `status`; fresh clone: `setup`
- Architecture check: `python tools/check_architecture.py`
- Documentation check: `python tools/check_docs.py` (`--fix` rotates old records)
""",

    "ARCHITECTURE.md": """# Architecture and Invariants

## Dependency Direction

```text
  data / schema / models
            ↓
  src/core (pure logic, deterministic computation, no side-effects)
            ↑
  src/storage ← src/runtime / services (orchestration, state management, persistence)
                      ↓
              src/presentation (view projection, animations)
                      ↓
                    src/ui (container layout, user interaction)
```

## Ownership

- Business state is owned and managed by Controllers/Services; state updates must be atomic.
- UI only captures intent and emits commands; it must NEVER bypass controllers to mutate state.
- Presentation only subscribes to or projects core snapshots; animation callbacks must not drive business logic.
- Storage encapsulates serialization, migrations, and integrity validation; rollback on save failures.

## Invariants

- `core` is pure deterministic logic, zero dependencies on platform APIs, I/O, networking, or views.
- State schemas support version migrations; refuse unknown/newer formats safely without corrupting backups.
- All feature changes must have automated tests protecting architectural boundaries.

## Verification & Reference

- [Architecture Check](tools/check_architecture.py) enforces dependency direction and core purity.
- Detailed domain rules are indexed in the [Documentation Index](docs/README.md).
""",

    # Multi-Agent Entrypoints pointing to AGENTS.md
    "CLAUDE.md": "@AGENTS.md\n",
    ".cursorrules": """# Cursor / Codex Rules
Read and strictly adhere to AGENTS.md and ARCHITECTURE.md before planning or modifying code.
All documentation and architectural invariants specified in AGENTS.md are enforced via pre-commit hooks and must be followed.
""",
    ".github/copilot-instructions.md": """# GitHub Copilot / Codex Instructions
Always read and strictly adhere to [AGENTS.md](../AGENTS.md) and [ARCHITECTURE.md](../ARCHITECTURE.md).
Do not violate core layer boundaries or documentation rules.
""",
    ".claude/settings.json": """{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell",
        "hooks": [
          {
            "type": "command",
            "shell": "bash",
            "command": "cd \\"$CLAUDE_PROJECT_DIR\\" && python tools/agent_guard.py",
            "timeout": 30,
            "statusMessage": "Git workflow guard"
          }
        ]
      }
    ]
  }
}
""",

    # Git hooks delegate to the main worktree's tools/git_guard.py (core.hooksPath is absolute, set by tools/runs.py setup).
    ".githooks/pre-commit": """#!/bin/sh
exec python "$(dirname "$0")/../tools/git_guard.py" pre-commit
""",
    ".githooks/commit-msg": """#!/bin/sh
exec python "$(dirname "$0")/../tools/git_guard.py" commit-msg "$1"
""",
    ".githooks/pre-merge-commit": """#!/bin/sh
exec python "$(dirname "$0")/../tools/git_guard.py" pre-merge-commit
""",
    ".githooks/pre-push": """#!/bin/sh
exec python "$(dirname "$0")/../tools/git_guard.py" pre-push "$@"
""",

    "docs/README.md": """# Documentation Index

## Current State

Navigation only. Consult on demand; do not load documents in bulk. Reading triggers live in [AGENTS](../AGENTS.md).

| Category | Entry Point |
| --- | --- |
| Roadmap (project plan) | [Roadmap](exec-plans/roadmap.md) |
| Planning Policy | [Planning Policy](exec-plans/README.md) |
| Work Modes (phase / runtime) | [Work Modes](work-modes.md) |
| Documentation Policy | [Documentation Policy](documentation-policy.md) |
| Autonomous Mode | [Autonomous Mode](autonomous-mode.md) |
| Test Responsibilities | [Test Responsibilities](../tests/README.md) |

## Records

""",

    "docs/documentation-policy.md": """# Documentation Policy

## Current State

Owner of documentation rules. `tools/check_docs.py` enforces them.

### Structure

- In `docs/` (excluding `archive/`), each Markdown file has exactly one `# Title`, then `## Current State` and `## Records`. Use level 3+ headings inside sections.
- Current State: current facts only, rewritten in place. No dates, hashes or test counts.
- Current State limit: 3,000 characters for owning policies, 2,000 for every other document.
- Records: `### YYYY-MM-DD Title`, newest first, at most 5 entries. `--fix` rotates older entries to `docs/archive/` and rewrites links.

### Writing Rules

Apply to `AGENTS.md`, `ARCHITECTURE.md` and `docs/` (not `archive/`). Checker-enforced rules are marked (checked).

- One fact or rule per line or bullet, at most 200 characters (checked; code blocks exempt).
- No filler or preamble such as `please note`, `in order to`, `it is important`; the checker's `FILLER` lists them (checked; inline code exempt).
- State a rule once, in its owning document; elsewhere link to it (checked for lines of 80+ characters).
- Imperative, present tense. Name the command, path or threshold; drop the reasoning unless the rule is unclear without it.
- Edit in place: replace or delete superseded text. Never append a correction or a "Note:" paragraph.
- Prefer lists and tables to paragraphs. Add an example only when the rule is ambiguous without it.
- Near a budget: shorten existing text first. Do not raise a limit to fit new text.

### Budgets

- `AGENTS.md` <= 4,000 characters; `ARCHITECTURE.md` <= 6,000 characters.
- Required reading (AGENTS, ARCHITECTURE, active plan) <= 10,000 characters.
- `AGENTS.md` is a map: always-on rules plus reading triggers. Detailed rules belong to the policy that owns them, not to AGENTS.

### Commands

- Check: `python tools/check_docs.py`
- Rotate old records: `python tools/check_docs.py --fix`, then review and stage both files.
- Pre-commit (automatic): `python tools/check_docs.py --staged`
- Fresh clone: `python tools/runs.py setup`

## Records

""",

    "docs/autonomous-mode.md": """# Autonomous Mode

## Current State

Applies to `/goal`, unattended tasks, batch runs, and multi-step goals without continuous human approval.

Read the [Planning Policy](exec-plans/README.md) too. Hard permission gates in [AGENTS](../AGENTS.md) always apply.

1. **Continuous Execution**: Do not halt for routine "what next" questions; keep executing toward the objective.
2. **Exploration Budget**: At most 3 distinct approaches or iterations unless the plan sets another budget. Stop and report if all fail.
3. **Pre-Registration**: Record each approach and its acceptance criteria in the active plan before substantive code changes.
4. **Phase Handoff**: After acceptance, do the Planning Policy handoff and `python tools/phase.py finish`; `start` the next phase if approved.
5. **Turn Heartbeat**: End every turn with `LOOP: attempt <k>/<N> | <current_state> | <verification_metric_or_blocker>`.

## Records

""",

    "docs/exec-plans/README.md": """# Planning Policy

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

""",

    "docs/work-modes.md": """# Work Modes

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

""",

    ".gitignore": """__pycache__/
*.py[cod]
# Runtime records: the orphan runs branch, checked out here by tools/runs.py setup.
/runs/
""",

    "docs/exec-plans/roadmap.md": """# Project Roadmap

## Current State

Goal: Project architecture bootstrap and roadmap definition.

Current Phase: 2

### Phases

1. Phase 1 Foundation: complete. Initial harness scaffold and governance established.
2. Phase 2 Core Implementation: pending. Define scope and acceptance criteria before activating.

### Approved Direction

- Decisions and architectural boundaries defined in [Architecture](../../ARCHITECTURE.md).
- Planning governance defined in the [Planning Policy](README.md).

## Records

""",

    "docs/exec-plans/active/.gitkeep": "",
    "docs/exec-plans/completed/.gitkeep": "",
    "docs/exec-plans/paused/.gitkeep": "",
    "docs/archive/.gitkeep": "",
    "src/core/.gitkeep": "",
    "src/ui/.gitkeep": "",

    "tests/README.md": """# Test Responsibilities

Tests are partitioned strictly by responsibility to avoid redundant coverage:

1. **Architecture (`tools/check_architecture.py`, tested by `tools/test_check_architecture.py`)**: Comment- and string-aware verification of core purity, forbidden dependencies, and UI layout constraints.
2. **Documentation Guard (`tools/test_check_docs.py`)**: Ensures documentation parser, planning rules and archive rotation continue to work.
3. **Workflow Guard (`tools/test_git_guard.py`)**: Main-branch commit rules, the agent command guard, and phase parsing.
4. **Unit & Integration Tests**: Verify `src/core/` algorithms, state transitions, and edge cases.

Run all checks via `python tools/verify.py`.
""",

    "tools/test_check_docs.py": """\"\"\"Documentation guard regression tests.\"\"\"
import unittest
from pathlib import Path
import check_docs as docs

class DocsRegressionTest(unittest.TestCase):
    def test_link_destination(self):
        self.assertEqual(docs.link_destination("docs/sub/a.md", "../b.md"), "docs/b.md")
        self.assertIsNone(docs.link_destination("docs/a.md", "http://example.com"))

    def test_headings_parsing(self):
        sample = "# Title\\n\\n## Current State\\n\\nFact.\\n\\n## Records\\n\\n### 2026-09-28 Title\\n\\nLog.\\n"
        state, entries, _ = docs.parse_document("test.md", sample)
        self.assertEqual(state, "Fact.")
        self.assertEqual(len(entries), 1)

class PlanningRulesTest(unittest.TestCase):
    ROADMAP = "# Roadmap\\n\\n## Current State\\n\\nCurrent Phase: 2\\n\\n- Phase 2: active, [plan](active/p2.md)\\n\\n## Records\\n"
    PLAN = "# P2\\n\\n## Current State\\n\\nStatus: x\\nNext Step: y\\nBlockers: none\\nRoadmap: Phase 2\\n\\n## Records\\n"

    def texts(self, **extra):
        texts = {docs.ROADMAP: self.ROADMAP, docs.ACTIVE_DIR + "p2.md": self.PLAN}
        texts.update(extra)
        return texts

    def test_valid_plan_passes(self):
        self.assertEqual(docs.check_planning(self.texts()), [])

    def test_no_active_plan_is_allowed(self):
        self.assertEqual(docs.check_planning({docs.ROADMAP: "# R\\n\\n## Current State\\n\\n- Phase 1\\n\\n## Records\\n"}), [])

    def test_missing_roadmap(self):
        errors = docs.check_planning({docs.ACTIVE_DIR + "p2.md": self.PLAN})
        self.assertIn("roadmap missing", errors[0])

    def test_two_active_plans(self):
        errors = docs.check_planning(self.texts(**{docs.ACTIVE_DIR + "p3.md": self.PLAN}))
        self.assertTrue(any("at most one active plan" in e for e in errors))

    def test_missing_roadmap_line(self):
        plan = self.PLAN.replace("Roadmap: Phase 2\\n", "")
        errors = docs.check_planning(self.texts(**{docs.ACTIVE_DIR + "p2.md": plan}))
        self.assertTrue(any('Roadmap: Phase <N>' in e for e in errors))

    def test_phase_not_in_roadmap(self):
        plan = self.PLAN.replace("Phase 2", "Phase 7")
        errors = docs.check_planning(self.texts(**{docs.ACTIVE_DIR + "p2.md": plan}))
        self.assertTrue(any("Phase 7 is not listed" in e for e in errors))

    def test_roadmap_must_link_active_plan(self):
        roadmap = self.ROADMAP.replace("[plan](active/p2.md)", "plan")
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any("must link to the active plan" in e for e in errors))

    def test_nested_files_count_as_active_plans(self):
        self.assertEqual(docs.active_plans({docs.ACTIVE_DIR + "sub/x.md": "", docs.ACTIVE_DIR + "a.md": ""}),
                         [docs.ACTIVE_DIR + "a.md", docs.ACTIVE_DIR + "sub/x.md"])

    def test_nested_plans_cannot_bypass_limit(self):
        texts = {docs.ROADMAP: self.ROADMAP, docs.ACTIVE_DIR + "a/p.md": self.PLAN, docs.ACTIVE_DIR + "b/p.md": self.PLAN}
        errors = docs.check_planning(texts)
        self.assertTrue(any("at most one active plan" in e for e in errors))

    def test_phase_only_in_records_fails(self):
        roadmap = ("# Roadmap\\n\\n## Current State\\n\\n- Phase 1: done\\n\\n## Records\\n\\n"
                   "### 2026-09-28 Old\\n\\n- Phase 2: active, [plan](active/p2.md)\\n")
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any("must link to the active plan" in e for e in errors))
        self.assertTrue(any("Phase 2 is not listed" in e for e in errors))

    def test_roadmap_line_only_in_plan_records_fails(self):
        plan = self.PLAN.replace("Roadmap: Phase 2\\n", "") + "\\n### 2026-09-28 Old\\n\\nRoadmap: Phase 2\\n"
        errors = docs.check_planning(self.texts(**{docs.ACTIVE_DIR + "p2.md": plan}))
        self.assertTrue(any('Roadmap: Phase <N>' in e for e in errors))

    def test_phase_line_must_link_plan(self):
        roadmap = self.ROADMAP.replace("- Phase 2: active, [plan](active/p2.md)",
                                       "- Phase 1: done, [plan](active/p2.md)\\n- Phase 2: active")
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any("Phase 2 line must link" in e for e in errors))

    def test_completed_phase_cannot_hold_active_plan(self):
        roadmap = self.ROADMAP.replace("Current Phase: 2", "Current Phase: 3").replace(
            "Phase 2: active", "Phase 2: complete")
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any("not the roadmap Current Phase 3" in e for e in errors))

    def test_missing_current_phase_marker(self):
        roadmap = self.ROADMAP.replace("Current Phase: 2\\n\\n", "")
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any('Current Phase: <N>' in e for e in errors))

    def test_malformed_roadmap_fails_closed(self):
        roadmap = self.ROADMAP + "loose text without a record heading\\n"
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any("must link to the active plan" in e for e in errors))

class WritingRulesTest(unittest.TestCase):
    def test_terse_document_passes(self):
        self.assertEqual(docs.check_writing({"docs/a.md": "# A\\n\\n- Run `python x.py`.\\n"}), [])

    def test_long_line_fails(self):
        errors = docs.check_writing({"docs/a.md": "# A\\n\\n" + "word " * 50 + "\\n"})
        self.assertTrue(any("docs/a.md:3:" in e and "one fact per line" in e for e in errors))

    def test_code_block_is_exempt(self):
        text = "# A\\n\\n```text\\n" + "x" * 300 + "\\nPlease note this.\\n```\\n"
        self.assertEqual(docs.check_writing({"docs/a.md": text}), [])

    def test_filler_fails_unless_inline_code(self):
        errors = docs.check_writing({"AGENTS.md": "# A\\n\\nPlease note that tests run first.\\n"})
        self.assertTrue(any('filler phrase' in e for e in errors))
        self.assertEqual(docs.check_writing({"AGENTS.md": "- Avoid `in order to`.\\n"}), [])

    def test_repeated_rule_across_documents_fails(self):
        rule = "- Phase work happens only in a phase worktree and reaches the main branch through a squash merge.\\n"
        errors = docs.check_writing({"AGENTS.md": rule, "docs/work-modes.md": rule})
        self.assertTrue(any("repeats" in e for e in errors))
        self.assertEqual(docs.check_writing({"docs/a.md": rule + rule}), [])

    def test_archive_is_exempt(self):
        self.assertEqual(docs.check_writing({"docs/archive/a.md": "Please note " + "x" * 300}), [])

    def test_policy_state_limit_is_higher(self):
        state = "- fact\\n" * 340  # about 2,380 characters
        doc = "# P\\n\\n## Current State\\n\\n" + state + "\\n## Records\\n"
        snapshot = type("S", (), {"texts": {}, "exists": lambda self, name: True})()
        for name, ok in ((docs.POLICIES[0], True), ("docs/other.md", False)):
            snapshot.texts = {name: doc}
            errors = [e for e in docs.check_snapshot(snapshot) if e.startswith(name + ": current state")]
            self.assertEqual(not errors, ok, name)

class RoutingRulesTest(unittest.TestCase):
    AGENTS = "".join(f"[p]({p})\\n" for p in docs.POLICIES)

    def texts(self, agents=None, skip=None):
        texts = {p: "" for p in docs.POLICIES if p != skip}
        texts["AGENTS.md"] = self.AGENTS if agents is None else agents
        return texts

    def test_all_policies_routed(self):
        self.assertEqual(docs.check_routes(self.texts()), [])

    def test_missing_route(self):
        agents = self.AGENTS.replace("[p](docs/autonomous-mode.md)\\n", "")
        errors = docs.check_routes(self.texts(agents=agents))
        self.assertTrue(any("must route to docs/autonomous-mode.md" in e for e in errors))

    def test_missing_policy_file(self):
        errors = docs.check_routes(self.texts(skip="docs/documentation-policy.md"))
        self.assertTrue(any("docs/documentation-policy.md: required policy document missing" in e for e in errors))

if __name__ == '__main__':
    unittest.main()
""",

    "tools/verify.py": """\"\"\"Single entrypoint for full project verification.\"\"\"
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_command(cmd, name):
    print(f"--> [Running] {name}...")
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        print(f"[FAIL] {name} failed!", file=sys.stderr)
        sys.exit(res.returncode)

def main():
    # 1. Documentation budget and planning invariants (working tree)
    run_command([sys.executable, "tools/check_docs.py"], "Documentation check")
    # 2. Architectural boundary check
    run_command([sys.executable, "tools/check_architecture.py"], "Architecture boundary check")
    # 3. Harness regression tests (tools/test_*.py)
    run_command([sys.executable, "-m", "unittest", "discover", "-s", "tools", "-p", "test_*.py"],
                "Harness regression tests")
    # 4. Domain unit tests (hook up your pytest / npm test / cargo test here)
    # run_command(["pytest"], "Unit tests")
    print("\\n[SUCCESS] All checks passed! Project is healthy.")

if __name__ == '__main__':
    main()
"""
}

# Embedded universal English version of check_docs.py
CHECK_DOCS_CODE = r'''"""Enforce bounded current docs; rotate history explicitly, check Git's index in hooks."""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LIMITS = {'AGENTS.md': 4000, 'ARCHITECTURE.md': 6000}
STATE_LIMIT = 2000          # roadmap, active plan, index and other docs
POLICY_STATE_LIMIT = 3000   # owning policies: read only when their trigger fires
MAX_LOG = 5
LINE_LIMIT = 200            # one fact per line; fenced code blocks are exempt
DUPLICATE_MIN = 80          # normalized lines this long may appear in one document only
FILLER = ('please note', 'note that', 'it is important', 'it should be noted', 'in order to',
          'make sure to', 'basically', 'as mentioned', 'as noted above', 'keep in mind', 'feel free',
          'needless to say', 'in other words', 'it is worth noting')
FILLER_RE = re.compile(r'\b(?:' + '|'.join(re.escape(f) for f in FILLER) + r')\b', re.I)
MANIFEST = 'docs/references/workflow-preservation.json'
ROADMAP = 'docs/exec-plans/roadmap.md'
ACTIVE_DIR = 'docs/exec-plans/active/'
POLICIES = ('docs/exec-plans/README.md', 'docs/documentation-policy.md', 'docs/autonomous-mode.md',
            'docs/work-modes.md')

def git(root, *args, data=None):
    return subprocess.run(['git', '-C', str(root), *args], input=data, capture_output=True, check=True).stdout

def is_document(name):
    return name in (*LIMITS, 'CLAUDE.md') or (name.startswith('docs/') and name.endswith('.md'))

class Snapshot:
    def __init__(self, root, staged=False):
        self.root, self.staged = root, staged
        self.texts = {}
        if staged:
            entries = git(root, 'ls-files', '--stage', '-z').split(b'\0')
            self.paths, blobs = set(), []
            for entry in filter(None, entries):
                meta, raw_name = entry.split(b'\t', 1)
                mode, oid, stage = meta.split()
                name = raw_name.decode('utf-8')
                self.paths.add(name)
                if stage != b'0':
                    raise ValueError(f'Unmerged index entry: {name}')
                if is_document(name) or name == MANIFEST:
                    if mode not in (b'100644', b'100755'):
                        raise ValueError(f'{name}: document must be a regular file.')
                    blobs.append((name, oid))
            output = git(root, 'cat-file', '--batch', data=b''.join(oid + b'\n' for _, oid in blobs))
            cursor = 0
            for name, _ in blobs:
                end = output.index(b'\n', cursor)
                size = int(output[cursor:end].split()[2])
                cursor = end + 1
                self.texts[name] = output[cursor:cursor + size].decode('utf-8-sig').replace('\r\n', '\n')
                cursor += size + 1
        else:
            paths = [root / name for name in (*LIMITS, 'CLAUDE.md')]
            if (root / MANIFEST).exists():
                paths.append(root / MANIFEST)
            paths += sorted((root / 'docs').rglob('*.md'))
            for path in paths:
                if path.is_file():
                    self.texts[path.relative_to(root).as_posix()] = path.read_text(encoding='utf-8-sig')
            self.paths = set(self.texts)

    def exists(self, name):
        if self.staged:
            return name in self.paths or any(p.startswith(name.rstrip('/') + '/') for p in self.paths)
        return (self.root / name).exists()

def headings(text):
    result, fence, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not line[marker.end():].strip():
                fence = None
        elif marker:
            fence = marker[1]
        else:
            match = re.match(r'^(#{1,6}) (.+?)\s*$', line)
            if match:
                result.append((len(match[1]), match[2], offset, offset + len(line)))
        offset += len(line)
    return result

def parse_document(name, text):
    marks = headings(text)
    top = [h for h in marks if h[0] <= 2]
    if (len(top) != 3 or top[0][0] != 1 or text[:top[0][2]].strip()
            or [h[1] for h in top[1:]] != ['Current State', 'Records'] or any(h[0] != 2 for h in top[1:])
            or text[top[0][3]:top[1][2]].strip()):
        raise ValueError(f'{name}: require one title, then exactly ## Current State and ## Records; use ### inside state.')
    state = text[top[1][3]:top[2][2]].strip()
    log_start = top[2][3]
    starts = [h for h in marks if h[0] == 3 and h[2] >= log_start]
    if text[log_start:starts[0][2] if starts else len(text)].strip():
        raise ValueError(f'{name}: record content requires a ### YYYY-MM-DD title heading.')
    entries, dates = [], []
    for i, h in enumerate(starts):
        match = re.fullmatch(r'(\d{4}-\d{2}-\d{2})\s+\S.*', h[1])
        if not match:
            raise ValueError(f'{name}: invalid record heading {h[1]!r}; use ### YYYY-MM-DD title.')
        try:
            dates.append(date.fromisoformat(match[1]))
        except ValueError as error:
            raise ValueError(f'{name}: invalid record date {match[1]}.') from error
        entries.append(text[h[2]:starts[i + 1][2] if i + 1 < len(starts) else len(text)])
    if dates != sorted(dates, reverse=True):
        raise ValueError(f'{name}: records must be newest first.')
    return state, entries, log_start

def link_destination(source, target):
    target = target.strip('<>')
    if target.startswith(('#', '/')) or re.match(r'^[a-zA-Z][\w+.-]*:', target):
        return None
    path = unquote(target.split('#', 1)[0])
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), path))

def check_snapshot(snapshot, allow_rotation=False):
    errors, texts = [], snapshot.texts
    for name, limit in LIMITS.items():
        if name not in texts:
            errors.append(f'{name}: required file missing.')
        elif len(texts[name]) > limit:
            errors.append(f'{name}: {len(texts[name])} characters > {limit}.')
    if texts.get('CLAUDE.md', '').strip() != '@AGENTS.md':
        errors.append('CLAUDE.md: keep the single shared entry @AGENTS.md.')
    required = [v for k, v in texts.items() if k in LIMITS or k.startswith('docs/exec-plans/active/')]
    if sum(map(len, required)) > 10000:
        errors.append('Required reading exceeds 10000 characters (AGENTS, ARCHITECTURE, active plans).')
    errors += check_writing(texts)
    for name, text in texts.items():
        if not is_document(name):
            continue
        for target in re.findall(r'\]\(([^)]+)\)', text):
            dest = link_destination(name, target)
            if dest is not None and not snapshot.exists(dest):
                errors.append(f'{name}: broken documentation link {target}')
        if not name.startswith('docs/') or name.startswith('docs/archive/'):
            continue
        try:
            state, entries, _ = parse_document(name, text)
        except ValueError as error:
            errors.append(str(error))
            continue
        limit = POLICY_STATE_LIMIT if name in POLICIES else STATE_LIMIT
        if not state or len(state) > limit:
            errors.append(f'{name}: current state must be 1..{limit} characters (got {len(state)}); rewrite in place.')
        if re.search(r'\b[0-9a-fA-F]{64}\b|\b20\d{2}-\d{2}-\d{2}\b|\b\d[\d,]*\s+(?:assertions|suites|tests)\b', state):
            errors.append(f'{name}: dates, hashes and test-result counts belong in records, not current state.')
        if len(entries) > MAX_LOG and not allow_rotation:
            errors.append(f'{name}: {len(entries)} records > {MAX_LOG}; run python tools/check_docs.py --fix, review and stage both files.')
        if name.startswith(ACTIVE_DIR):
            opening = '\n'.join(state.splitlines()[:8])
            for label in ('Status:', 'Next Step:', 'Blockers:', 'Roadmap:'):
                if label not in opening:
                    errors.append(f'{name}: missing opening {label}')
    errors += check_planning(texts)
    errors += check_routes(texts)
    return errors

def prose_lines(text):
    """Yield (number, line) outside fenced code blocks."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not line[marker.end():].strip():
                fence = None
        elif marker:
            fence = marker[1]
        else:
            yield number, line

def check_writing(texts):
    """Terse writing: one fact per line, no filler phrases, each long rule stated in one document only."""
    errors, seen = [], {}
    for name in sorted(texts):
        if not is_document(name) or name == 'CLAUDE.md' or name.startswith('docs/archive/'):
            continue
        for number, line in prose_lines(texts[name]):
            if len(line) > LINE_LIMIT:
                errors.append(f'{name}:{number}: line has {len(line)} characters > {LINE_LIMIT}; one fact per line.')
            filler = FILLER_RE.search(re.sub(r'`[^`]*`', '', line))
            if filler:
                errors.append(f'{name}:{number}: filler phrase "{filler[0]}"; state the rule directly.')
            key = re.sub(r'\s+', ' ', re.sub(r'^\s*(?:[-*+]|\d+\.)\s+', '', line)).strip().lower()
            if len(key) < DUPLICATE_MIN:
                continue
            if key in seen and seen[key][0] != name:
                errors.append(f'{name}:{number}: repeats {seen[key][0]}:{seen[key][1]}; keep the rule in its owner and link to it.')
            seen.setdefault(key, (name, number))
    return errors

def check_routes(texts):
    """AGENTS.md is a map: every owning policy must exist and be routed from it."""
    errors, routes = [], links_in('AGENTS.md', texts.get('AGENTS.md', ''))
    for policy in POLICIES:
        if policy not in texts:
            errors.append(f'{policy}: required policy document missing.')
        elif policy not in routes:
            errors.append(f'AGENTS.md: Required Reading must route to {policy}.')
    return errors

def active_plans(texts):
    """Every Markdown file under active/, nested or not, counts as an active plan."""
    return sorted(k for k in texts if k.startswith(ACTIVE_DIR) and k.endswith('.md'))

def current_state(name, text):
    """Current State section only, so Records history cannot satisfy planning checks."""
    try:
        return parse_document(name, text)[0]
    except ValueError:
        return ''  # fail closed; check_snapshot reports the structure error

def links_in(source, text):
    return {link_destination(source, target) for target in re.findall(r'\]\(([^)]+)\)', text)}

def check_planning(texts):
    """Roadmap is the single project plan; at most one active plan, tied to the roadmap Current Phase."""
    if ROADMAP not in texts:
        return [f'{ROADMAP}: required project roadmap missing.']
    errors, plans, roadmap = [], active_plans(texts), current_state(ROADMAP, texts[ROADMAP])
    if len(plans) > 1:
        errors.append(f'{ACTIVE_DIR}: at most one active plan allowed (found {len(plans)}: {", ".join(plans)}).')
    linked = links_in(ROADMAP, roadmap)
    current = re.search(r'^Current Phase:\s*(\w+)\.?\s*$', roadmap, re.M)
    for plan in plans:
        opening = '\n'.join(current_state(plan, texts[plan]).splitlines()[:8])
        match = re.search(r'^Roadmap:\s*Phase\s+(\w+)\.?\s*$', opening, re.M)
        if plan not in linked:
            errors.append(f'{ROADMAP}: must link to the active plan {plan}.')
        if not match:
            errors.append(f'{plan}: opening line must read "Roadmap: Phase <N>".')
            continue
        if not current:
            errors.append(f'{ROADMAP}: Current State must declare "Current Phase: <N>".')
        elif current[1] != match[1]:
            errors.append(f'{plan}: Phase {match[1]} is not the roadmap Current Phase {current[1]}.')
        phase_lines = [line for line in roadmap.splitlines() if re.search(rf'\bPhase {re.escape(match[1])}\b', line)]
        if not phase_lines:
            errors.append(f'{plan}: Phase {match[1]} is not listed in {ROADMAP} Current State.')
        elif plan in linked and not any(plan in links_in(ROADMAP, line) for line in phase_lines):
            errors.append(f'{ROADMAP}: the Phase {match[1]} line must link to the active plan {plan}.')
    return errors

def check_docs(root: Path, staged=False) -> list[str]:
    try:
        return check_snapshot(Snapshot(root, staged))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        return [f'Document snapshot failed: {error}']

def rebase_links(text, source, destination):
    def replace(match):
        target = match[1].strip('<>')
        dest = link_destination(source, target)
        if dest is None:
            if not target.startswith('#'):
                return match[0]
            value = posixpath.relpath(source, posixpath.dirname(destination)) + target
        else:
            anchor = '#' + target.split('#', 1)[1] if '#' in target else ''
            value = posixpath.relpath(dest, posixpath.dirname(destination)) + anchor
        return '](' + ('<' + value + '>' if re.search(r'\s', value) else value) + ')'
    return re.sub(r'\]\(([^)]+)\)', replace, text)

def atomic_write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.docs-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def rotate_logs(root):
    snapshot = Snapshot(root)
    errors = check_snapshot(snapshot, allow_rotation=True)
    if errors:
        return errors, []
    changed = []
    for name, text in snapshot.texts.items():
        if not name.startswith('docs/') or name.startswith('docs/archive/') or not name.endswith('.md'):
            continue
        _, entries, start = parse_document(name, text)
        if len(entries) <= MAX_LOG:
            continue
        archive = 'docs/archive/' + name.removeprefix('docs/')
        previous = snapshot.texts.get(archive, '# ' + PurePosixPath(name).stem + ': Historical Records\n\n')
        counts, moved = Counter(), []
        for entry in entries[MAX_LOG:]:
            counts[entry] += 1
            identity = hashlib.sha256(f'{name}\0{entry}\0{counts[entry]}'.encode('utf-8')).hexdigest()
            marker = f'<!-- docs-archive-id:{identity} -->'
            if marker not in previous:
                first, rest = rebase_links(entry, name, archive).split('\n', 1)
                moved.append(first + '\n' + marker + '\n' + rest)
        if moved:
            atomic_write(root, archive, previous.rstrip() + '\n\n' + '\n\n'.join(moved))
        pointer = posixpath.relpath(archive, posixpath.dirname(name))
        keep = entries[:MAX_LOG]
        if '](' + pointer + ')' not in ''.join(keep):
            keep[-1] = keep[-1].rstrip() + f'\n\n[Older Records]({pointer})\n\n'
        atomic_write(root, name, text[:start] + '\n' + ''.join(keep))
        changed.append(name)
    return check_docs(root), changed

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--fix', action='store_true', help='Rotate old records in working tree.')
    modes.add_argument('--staged', action='store_true', help='Validate only Git index contents (pre-commit).')
    args = parser.parse_args()
    try:
        errors, changed = rotate_logs(ROOT) if args.fix else (check_docs(ROOT, args.staged), [])
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        errors, changed = [str(error)], []
    if errors:
        print('\n'.join(errors))
        return 1
    print('docs OK' + (f' (rotated {len(changed)} files; review and stage changes)' if changed else ''))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'''

FILES["tools/check_docs.py"] = CHECK_DOCS_CODE

CHECK_ARCHITECTURE_CODE = r'''"""Executable architectural boundary checks.

Comments and string literals are ignored, so prose that mentions `http.` or
`window.` does not fail the build. Python is checked through its AST; other
languages through a comment/string-aware scanner. Documentation checks live in
check_docs.py and run separately (verify.py, pre-commit).
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = 'src/core'
UI_DIR = 'src/ui'

# Core is pure deterministic logic: no file system, process, OS, network, persistence or UI dependencies.
PY_FORBIDDEN_MODULES = {
    'os', 'shutil', 'pathlib', 'glob', 'tempfile', 'subprocess', 'multiprocessing', 'socket', 'ssl',
    'select', 'http', 'urllib', 'requests', 'httpx', 'aiohttp', 'websockets', 'sqlite3', 'pickle',
    'shelve', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'pygame', 'kivy', 'flask', 'django',
    'fastapi',
}
PY_FORBIDDEN_CALLS = {'open', 'input', '__import__'}
JS_FORBIDDEN_MODULES = {
    'fs', 'fs/promises', 'http', 'https', 'http2', 'net', 'tls', 'dgram', 'child_process', 'os',
    'worker_threads', 'axios', 'node-fetch', 'got', 'ws', 'react-dom', 'electron',
}
JS_FORBIDDEN_GLOBALS = {
    'fetch', 'XMLHttpRequest', 'WebSocket', 'EventSource', 'localStorage', 'sessionStorage',
    'indexedDB', 'document', 'window', 'navigator', 'process',
}
GO_FORBIDDEN_IMPORTS = {'os', 'net', 'syscall', 'io/ioutil', 'database/sql'}
RS_FORBIDDEN = r'\b(?:std::(?:fs|net|process|env)|tokio::(?:fs|net|process)|reqwest|hyper|ureq)\b'
GD_FORBIDDEN = (r'(?<![\w.])(?:FileAccess|DirAccess|HTTPRequest|HTTPClient|OS|Input|ResourceLoader|'
                r'ResourceSaver|JavaScriptBridge)\b|\bget_(?:tree|node)\s*\(')
UI_FORBIDDEN = (r'position\s*:\s*[\'"]?\s*absolute\b|\boffset_(?:left|right|top|bottom)\s*=|'
                r'\.place\(\s*x\s*=')

C_STYLE = {'line': ('//',), 'block': (('/*', '*/'),)}
LANGS = {
    '.py': {'line': ('#',), 'block': (), 'quotes': '\'"'},
    '.gd': {'line': ('#',), 'block': (), 'quotes': '\'"'},
    '.js': {**C_STYLE, 'quotes': '\'"`'},
    '.jsx': {**C_STYLE, 'quotes': '\'"`'},
    '.mjs': {**C_STYLE, 'quotes': '\'"`'},
    '.cjs': {**C_STYLE, 'quotes': '\'"`'},
    '.ts': {**C_STYLE, 'quotes': '\'"`'},
    '.tsx': {**C_STYLE, 'quotes': '\'"`'},
    '.vue': {'line': ('//',), 'block': (('/*', '*/'), ('<!--', '-->')), 'quotes': '\'"`'},
    '.svelte': {'line': ('//',), 'block': (('/*', '*/'), ('<!--', '-->')), 'quotes': '\'"`'},
    '.go': {**C_STYLE, 'quotes': '"`\''},
    '.rs': {**C_STYLE, 'quotes': '"'},
    '.css': {'line': (), 'block': (('/*', '*/'),), 'quotes': '\'"'},
    '.scss': {**C_STYLE, 'quotes': '\'"'},
}
JS_LIKE = {'.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.vue', '.svelte'}

def blank(segment):
    return re.sub(r'[^\n]', ' ', segment)

def strip_source(text, line=(), block=(), quotes=''):
    """Return (no_comments, code_only). Both keep offsets and newlines; code_only also blanks strings."""
    keep, code, i, n = [], [], 0, len(text)
    while i < n:
        opener = next((c for c in line if text.startswith(c, i)), None)
        if opener:
            end = text.find('\n', i)
            end = n if end < 0 else end
            keep.append(blank(text[i:end])); code.append(blank(text[i:end])); i = end
            continue
        pair = next((b for b in block if text.startswith(b[0], i)), None)
        if pair:
            end = text.find(pair[1], i + len(pair[0]))
            end = n if end < 0 else end + len(pair[1])
            keep.append(blank(text[i:end])); code.append(blank(text[i:end])); i = end
            continue
        if text[i] in quotes:
            quote, j = text[i], i + 1
            while j < n and text[j] != quote:
                j += 2 if text[j] == '\\' else 1
            end = min(j + 1, n)
            keep.append(text[i:end]); code.append(blank(text[i:end])); i = end
            continue
        keep.append(text[i]); code.append(text[i]); i += 1
    return ''.join(keep), ''.join(code)

def line_of(text, offset):
    return text.count('\n', 0, offset) + 1

def py_core_violations(text):
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return [(error.lineno or 1, f'cannot parse Python: {error.msg}')]
    found = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id in PY_FORBIDDEN_CALLS):
            found.append((node.lineno, f'forbidden call {node.func.id}()'))
        for name in names:
            if name.split('.')[0] in PY_FORBIDDEN_MODULES:
                found.append((node.lineno, f'forbidden import {name}'))
    return found

def js_module_root(spec):
    spec = spec.removeprefix('node:')
    if spec in JS_FORBIDDEN_MODULES:
        return spec
    parts = spec.split('/')
    return '/'.join(parts[:2]) if spec.startswith('@') else parts[0]

def core_violations(suffix, text):
    """List (line, message) for impure dependencies in a core source file."""
    if suffix == '.py':
        return py_core_violations(text)
    if suffix not in LANGS:
        return []
    no_comments, code = strip_source(text, **LANGS[suffix])
    found = []
    if suffix in JS_LIKE:
        imports = (r'\bfrom\s*([\'"])(.+?)\1|\bimport\s*\(?\s*([\'"])(.+?)\3|\brequire\s*\(\s*([\'"])(.+?)\5')
        for match in re.finditer(imports, no_comments):
            if code[match.start()] == ' ':
                continue  # the keyword itself sits inside a string literal
            spec = match[2] or match[4] or match[6]
            if js_module_root(spec) in JS_FORBIDDEN_MODULES:
                found.append((line_of(text, match.start()), f'forbidden import {spec}'))
        globals_ = '|'.join(sorted(JS_FORBIDDEN_GLOBALS))
        for match in re.finditer(rf'(?<![\w$.])({globals_})(?![\w$])', code):
            found.append((line_of(text, match.start()), f'forbidden global {match[1]}'))
    elif suffix == '.go':
        specs = []
        for match in re.finditer(r'\bimport\s*\(([^)]*)\)', no_comments):
            specs += [(match.start(), s) for s in re.findall(r'"([^"]+)"', match[1])]
        specs += [(m.start(), m[1]) for m in re.finditer(r'\bimport\s+(?:\w+\s+)?"([^"]+)"', no_comments)]
        for offset, spec in specs:
            if any(spec == bad or spec.startswith(bad + '/') for bad in GO_FORBIDDEN_IMPORTS):
                found.append((line_of(text, offset), f'forbidden import {spec}'))
    elif suffix == '.rs':
        for match in re.finditer(RS_FORBIDDEN, code):
            found.append((line_of(text, match.start()), f'forbidden dependency {match[0]}'))
    elif suffix == '.gd':
        for match in re.finditer(GD_FORBIDDEN, code):
            found.append((line_of(text, match.start()), f'forbidden engine API {match[0].strip()}'))
    return found

def ui_violations(suffix, text):
    """List (line, message) for hardcoded screen positions in a UI source file."""
    if suffix not in LANGS:
        return []
    no_comments, _ = strip_source(text, **LANGS[suffix])
    return [(line_of(text, m.start()), f'hardcoded position {m[0].strip()!r}; use layout containers')
            for m in re.finditer(UI_FORBIDDEN, no_comments)]

def scan(root=ROOT):
    errors = []
    for folder, check in ((CORE_DIR, core_violations), (UI_DIR, ui_violations)):
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(p for p in base.rglob('*') if p.is_file()):
            text = path.read_text(encoding='utf-8', errors='replace')
            for line, message in check(path.suffix.lower(), text):
                errors.append(f'{path.relative_to(root).as_posix()}:{line}: {message}')
    return errors

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    errors = scan()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        print(f'architecture FAILED ({len(errors)} violations); see ARCHITECTURE.md', file=sys.stderr)
        return 1
    print('architecture OK')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'''

FILES["tools/check_architecture.py"] = CHECK_ARCHITECTURE_CODE

TEST_CHECK_ARCHITECTURE_CODE = r'''"""Architecture checker regression tests: real violations fail, prose and strings do not."""
import tempfile
import unittest
from pathlib import Path
import check_architecture as arch

def messages(found):
    return [message for _, message in found]

class CorePythonTest(unittest.TestCase):
    def test_forbidden_import_fails(self):
        self.assertIn('forbidden import requests', messages(arch.core_violations('.py', 'import requests\n')))
        self.assertIn('forbidden import http.client', messages(arch.core_violations('.py', 'from http.client import X\n')))

    def test_forbidden_call_fails(self):
        self.assertEqual(arch.core_violations('.py', 'data = open("x")\n'), [(1, 'forbidden call open()')])

    def test_comments_and_strings_pass(self):
        text = '# uses http. and window. in prose\nNOTE = "requests.get socket fetch("\n"""import os"""\n'
        self.assertEqual(arch.core_violations('.py', text), [])

    def test_similar_names_pass(self):
        self.assertEqual(arch.core_violations('.py', 'import osmosis\nfrom .os import x\nsocket_count = 1\n'), [])

    def test_syntax_error_fails_closed(self):
        self.assertTrue(arch.core_violations('.py', 'def broken(:\n'))

class CoreScriptTest(unittest.TestCase):
    def test_js_imports_fail(self):
        text = "import axios from 'axios';\nconst fs = require('node:fs');\nimport('child_process');\n"
        self.assertEqual(messages(arch.core_violations('.ts', text)),
                         ['forbidden import axios', 'forbidden import node:fs', 'forbidden import child_process'])

    def test_js_globals_fail(self):
        found = arch.core_violations('.js', 'const w = window.innerWidth;\nfetch(url);\n')
        self.assertEqual(found, [(1, 'forbidden global window'), (2, 'forbidden global fetch')])

    def test_js_comments_strings_properties_pass(self):
        text = ("// call fetch( and window. here\n/* import x from 'axios' */\n"
                "const s = 'window.fetch http.get';\nconst t = `document`;\nstate.window = 1;\n")
        self.assertEqual(arch.core_violations('.ts', text), [])

    def test_go_imports(self):
        bad = 'package core\nimport (\n  "strings"\n  "net/http"\n)\n'
        self.assertEqual(messages(arch.core_violations('.go', bad)), ['forbidden import net/http'])
        self.assertEqual(arch.core_violations('.go', 'package core\n// import "os"\nimport "strings"\n'), [])

    def test_rust_and_gdscript(self):
        self.assertTrue(arch.core_violations('.rs', 'use std::fs::read;\n'))
        self.assertEqual(arch.core_violations('.rs', '// std::fs is banned\nlet s = "std::net";\n'), [])
        self.assertTrue(arch.core_violations('.gd', 'var f = FileAccess.open(p, 1)\n'))
        self.assertEqual(arch.core_violations('.gd', '# FileAccess is banned\nvar s = "OS"\n'), [])

class UiTest(unittest.TestCase):
    def test_absolute_position_fails(self):
        self.assertTrue(arch.ui_violations('.tsx', "const s = { position: 'absolute' };\n"))
        self.assertTrue(arch.ui_violations('.css', '.a { position: absolute; }\n'))
        self.assertTrue(arch.ui_violations('.gd', 'offset_left = 10\n'))

    def test_comments_pass(self):
        self.assertEqual(arch.ui_violations('.css', '/* never position: absolute */\n.a { display: flex; }\n'), [])
        self.assertEqual(arch.ui_violations('.gd', '# offset_left = 10\n'), [])

class ScanTest(unittest.TestCase):
    def test_scan_reports_path_and_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src/core').mkdir(parents=True)
            (root / 'src/core/a.py').write_text('x = 1\nimport socket\n', encoding='utf-8')
            self.assertEqual(arch.scan(root), ['src/core/a.py:2: forbidden import socket'])

if __name__ == '__main__':
    unittest.main()
'''

FILES["tools/test_check_architecture.py"] = TEST_CHECK_ARCHITECTURE_CODE

GIT_GUARD_CODE = r'''"""Git hook entrypoint for the Phase / Runtime workflow (owner: docs/work-modes.md).

Hooks live in the main worktree (core.hooksPath is absolute, set by tools/runs.py setup), so they
also run in phase worktrees and in the runs worktree.

Main branch (git config harness.mainBranch):
  - pre-commit: only a phase squash merge in progress (or the first commit); then docs and architecture checks;
  - commit-msg: "phase(<N>): <summary>", concise;
  - pre-merge-commit: refuse merge commits (squash only).
Runs branch (git config harness.runsBranch, default runs): runtime records, free-form commits.
Every branch except runs: never stage the runs/ worktree path.
pre-push: main receives only phase squash commits; main and runs never share history.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTECTED = ('main', 'master')
DEFAULT_RUNS_BRANCH = 'runs'
RUNS_DIR = 'runs'
ZERO = '0' * 40
PHASE_SUBJECT = re.compile(r'^phase\((\d+)\): \S.{0,59}$')
TRAILER = re.compile(r'^[A-Za-z][A-Za-z0-9-]*: \S')
MAX_BODY_LINES = 5

def git(*args, cwd=None, check=True):
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    if result.returncode:
        if check:
            raise RuntimeError(f'git {" ".join(args)} failed: {result.stderr.strip()}')
        return None
    return result.stdout.strip()

def config(key, cwd=None):
    return git('config', '--get', key, cwd=cwd, check=False) or ''

def protected_branches(cwd=None):
    value = config('harness.mainBranch', cwd)
    return (value,) if value else DEFAULT_PROTECTED

def runs_branch(cwd=None):
    return config('harness.runsBranch', cwd) or DEFAULT_RUNS_BRANCH

def current_branch(cwd=None):
    return git('symbolic-ref', '--short', '-q', 'HEAD', cwd=cwd, check=False) or ''

def head_exists(cwd=None):
    return git('rev-parse', '-q', '--verify', 'HEAD', cwd=cwd, check=False) is not None

def git_state(name, cwd=None):
    return Path(cwd or '.', git('rev-parse', '--git-path', name, cwd=cwd)).exists()

def runs_paths(paths):
    """Staged paths that belong to the runs worktree and must never enter another branch."""
    return [p for p in paths if p == RUNS_DIR or p.startswith(RUNS_DIR + '/')]

def message_errors(text):
    """Validate a main-branch squash message: phase subject, short optional body, trailers allowed."""
    lines = [line.rstrip() for line in text.splitlines() if not line.startswith('#')]
    while lines and not lines[-1]:
        lines.pop()
    while lines and not lines[0]:
        lines.pop(0)
    if not lines:
        return ['empty commit message']
    subject, body = lines[0], lines[1:]
    errors = []
    if not PHASE_SUBJECT.match(subject):
        errors.append(f'subject must read "phase(<N>): <summary>" (at most 72 characters), got {subject!r}')
    if body and body[0]:
        errors.append('separate the subject and the body with a blank line')
    prose = [line for line in body if line and not TRAILER.match(line)]
    if len(prose) > MAX_BODY_LINES:
        errors.append(f'body has {len(prose)} lines > {MAX_BODY_LINES}; keep the main-branch message concise')
    return errors

def fail(errors, hint):
    print('\n'.join(f'[git_guard] {e}' for e in errors), file=sys.stderr)
    print(f'[git_guard] {hint}', file=sys.stderr)
    return 1

def run_checks():
    top = git('rev-parse', '--show-toplevel')
    for script, args in (('tools/check_docs.py', ['--staged']), ('tools/check_architecture.py', [])):
        if subprocess.run([sys.executable, str(Path(top, script)), *args], cwd=top).returncode:
            return fail([f'{script} failed'], 'Fix the reported problems before committing.')
    return 0

def pre_commit():
    branch = current_branch()
    if branch == runs_branch():
        return 0
    staged = git('diff', '--cached', '--name-only', '--no-renames', '-z').split('\0')
    leaked = runs_paths(staged)
    if leaked:
        return fail([f'{branch or "HEAD"} stages runs worktree path {p}' for p in leaked],
                    f'Runtime records belong to the {runs_branch()} branch: python tools/runs.py record <id> "<summary>"')
    if branch not in protected_branches():
        return 0  # phase branches commit freely
    if not head_exists():
        return run_checks()
    if git_state('MERGE_HEAD'):
        return fail([f'merge commit on {branch}'], 'Main accepts only squash merges: python tools/phase.py finish "<summary>"')
    if not git_state('SQUASH_MSG'):
        return fail([f'direct commit on {branch}'],
                    'Main receives only phase squash commits. Phase work: python tools/phase.py start <slug>. '
                    'Runtime records: python tools/runs.py record <id> "<summary>".')
    return run_checks()

def commit_msg(path):
    if current_branch() not in protected_branches() or not head_exists():
        return 0
    errors = message_errors(Path(path).read_text(encoding='utf-8', errors='replace'))
    return fail(errors, 'See docs/work-modes.md.') if errors else 0

def pre_merge_commit():
    branch = current_branch()
    if branch in protected_branches():
        return fail([f'merge commit on {branch}'],
                    'Use python tools/phase.py finish (squash). To sync a remote, use git pull --rebase or --ff-only.')
    return 0

def commit_errors(sha):
    parents = git('rev-list', '--parents', '-n', '1', sha).split()[1:]
    if not parents:
        return []  # root commit
    if len(parents) > 1:
        return [f'{sha[:10]}: merge commit; the main branch accepts only phase squash commits']
    return [f'{sha[:10]}: {e}' for e in message_errors(git('log', '-1', '--format=%B', sha))]

def shared_history(main_sha, runs_sha):
    return bool(main_sha and runs_sha and git('merge-base', main_sha, runs_sha, check=False))

def pre_push(remote, lines):
    protected, runs, errors = protected_branches(), runs_branch(), []
    baseline = config('harness.baseline')
    tips = {}
    for line in lines:
        parts = line.split()
        if len(parts) != 4 or parts[1] == ZERO:
            continue
        _, local_sha, remote_ref, remote_sha = parts
        name = remote_ref.removeprefix('refs/heads/')
        if name == runs:
            tips['runs'] = local_sha
        if name not in protected:
            continue
        tips['main'] = local_sha
        exclude = ['--not', f'--remotes={remote}']
        if remote_sha != ZERO and git('cat-file', '-e', remote_sha + '^{commit}', check=False) is not None:
            exclude.append(remote_sha)
        if baseline:
            exclude.append(baseline)
        for sha in git('rev-list', local_sha, *exclude).split():
            errors += commit_errors(sha)
    main_tip = tips.get('main') or git('rev-parse', '-q', '--verify', protected[0], check=False)
    runs_tip = tips.get('runs') or git('rev-parse', '-q', '--verify', runs, check=False)
    if tips and shared_history(main_tip, runs_tip):
        errors.append(f'{protected[0]} and {runs} share history; never merge between them')
    return fail(errors, 'See docs/work-modes.md.') if errors else 0

def main(argv):
    if hasattr(sys.stderr, 'reconfigure'):
        try:
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    hook = argv[1] if len(argv) > 1 else ''
    try:
        if hook == 'pre-commit':
            return pre_commit()
        if hook == 'commit-msg':
            return commit_msg(argv[2])
        if hook == 'pre-merge-commit':
            return pre_merge_commit()
        if hook == 'pre-push':
            return pre_push(argv[2] if len(argv) > 2 else '', sys.stdin.read().splitlines())
    except (OSError, RuntimeError, IndexError) as error:
        return fail([str(error)], 'git_guard failed closed.')
    return fail([f'unknown hook {hook!r}'], 'usage: git_guard.py pre-commit|commit-msg <file>|pre-merge-commit|pre-push <remote>')

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
'''

FILES["tools/git_guard.py"] = GIT_GUARD_CODE

PHASE_CODE = r'''"""Phase workflow: one git worktree per roadmap phase, squash-merged to the main branch as one commit.

  python tools/phase.py start <slug>        create phase/<N>-<slug> in a sibling worktree (N = roadmap Current Phase)
  python tools/phase.py status              show the phase branch and worktree
  python tools/phase.py finish "<summary>"  verify, squash-merge as "phase(<N>): <summary>", remove worktree and branch
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import git_guard as guard

ROADMAP = 'docs/exec-plans/roadmap.md'
PREFIX = 'phase/'
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
BRANCH = re.compile(r'^phase/(\d+)-[a-z0-9-]+$')

class PhaseError(Exception):
    pass

def git(*args, cwd):
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise PhaseError(f'git {" ".join(args)} failed:\n{(result.stderr or result.stdout).strip()}')
    return result.stdout.strip()

def worktrees(cwd):
    """List of (path, branch) from git worktree list; the first entry is the main worktree."""
    items, path = [], None
    for line in git('worktree', 'list', '--porcelain', cwd=cwd).splitlines():
        if line.startswith('worktree '):
            path = Path(line[9:])
            items.append([path, ''])
        elif line.startswith('branch ') and items:
            items[-1][1] = line[7:].removeprefix('refs/heads/')
    return [tuple(item) for item in items]

def main_worktree(cwd):
    path, branch = worktrees(cwd)[0]
    if branch not in guard.protected_branches(path):
        raise PhaseError(f'main worktree {path} must have the main branch checked out (found {branch or "detached"}).')
    return path, branch

def current_phase(text):
    match = re.search(r'^Current Phase:\s*(\d+)\.?\s*$', text, re.M)
    if not match:
        raise PhaseError(f'{ROADMAP} must declare "Current Phase: <N>".')
    return int(match[1])

def phase_branches(cwd):
    output = git('for-each-ref', '--format=%(refname:short)', 'refs/heads/' + PREFIX, cwd=cwd)
    return [b for b in output.splitlines() if b]

def clean(cwd, untracked=True):
    args = ['status', '--porcelain'] + ([] if untracked else ['--untracked-files=no'])
    return not git(*args, cwd=cwd)

def start(slug, cwd):
    if not SLUG.match(slug):
        raise PhaseError('slug must be lowercase words joined by hyphens, e.g. subtitle-pipeline.')
    main, branch = main_worktree(cwd)
    existing = phase_branches(main)
    if existing:
        raise PhaseError(f'one phase at a time; finish or remove {", ".join(existing)} first.')
    if not guard.head_exists(main):
        raise PhaseError('commit the initial scaffold on the main branch first.')
    number = current_phase(git('show', f'HEAD:{ROADMAP}', cwd=main))
    name = f'{PREFIX}{number}-{slug}'
    path = main.parent / f'{main.name}.worktrees' / f'phase-{number}-{slug}'
    git('worktree', 'add', '-b', name, str(path), branch, cwd=main)
    print(f'Phase {number} started on {name}\n  worktree: {path}\n'
          f'Work and commit only in that worktree. Finish with: python tools/phase.py finish "<summary>"')

def status(cwd):
    main, branch = main_worktree(cwd)
    paths = {b: p for p, b in worktrees(main)}
    print(f'main: {branch} at {main} (roadmap Current Phase {current_phase(git("show", f"HEAD:{ROADMAP}", cwd=main))})')
    for name in phase_branches(main) or ['(no phase branch)']:
        print(f'phase: {name} at {paths.get(name, "(no worktree)")}')

def finish(summary, cwd, keep=False):
    main, branch = main_worktree(cwd)
    names = phase_branches(main)
    if len(names) != 1:
        raise PhaseError(f'expected exactly one phase branch, found {names or "none"}.')
    name = names[0]
    match = BRANCH.match(name)
    if not match:
        raise PhaseError(f'{name}: branch name must be phase/<N>-<slug>.')
    number = int(match[1])
    message = f'phase({number}): {summary.strip()}'
    errors = guard.message_errors(message)
    if errors:
        raise PhaseError('; '.join(errors))
    path = {b: p for p, b in worktrees(main)}.get(name)
    if path is None:
        raise PhaseError(f'{name} has no worktree; recreate it with git worktree add.')
    if not clean(path):
        raise PhaseError(f'{path} has uncommitted or untracked changes; commit or remove them first.')
    if not clean(main, untracked=False):
        raise PhaseError(f'main worktree {main} has uncommitted changes.')
    if subprocess.run(['git', 'merge-base', '--is-ancestor', branch, name], cwd=main).returncode:
        raise PhaseError(f'{branch} moved since the phase started. In {path} run: git merge {branch}, '
                         're-verify, commit, then finish again.')
    if git('rev-list', '--count', f'{branch}..{name}', cwd=main) == '0':
        raise PhaseError(f'{name} has no commits beyond {branch}.')
    if current_phase(git('show', f'{name}:{ROADMAP}', cwd=main)) == number:
        raise PhaseError(f'roadmap on {name} still says Current Phase: {number}. Complete the Planning Policy '
                         'handoff in the worktree first.')
    print(f'--> verifying {name} in {path}')
    if subprocess.run([sys.executable, 'tools/verify.py'], cwd=path).returncode:
        raise PhaseError('verification failed in the phase worktree; nothing was merged.')
    git('merge', '--squash', name, cwd=main)
    committed = subprocess.run(['git', 'commit', '-m', message], cwd=main)
    if committed.returncode:
        subprocess.run(['git', 'reset', '--merge'], cwd=main)
        raise PhaseError('squash commit rejected by the hooks; the main branch is unchanged.')
    print(f'Merged {name} into {branch} as: {message}')
    if not keep:
        git('worktree', 'remove', str(path), cwd=main)
        git('branch', '-D', name, cwd=main)
        print(f'Removed worktree {path} and branch {name}.')

def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('start').add_argument('slug')
    commands.add_parser('status')
    end = commands.add_parser('finish')
    end.add_argument('summary')
    end.add_argument('--keep', action='store_true', help='keep the worktree and branch after merging')
    args = parser.parse_args(argv)
    cwd = Path.cwd()
    try:
        if args.command == 'start':
            start(args.slug, cwd)
        elif args.command == 'status':
            status(cwd)
        else:
            finish(args.summary, cwd, args.keep)
    except PhaseError as error:
        print(f'[phase] {error}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'''

FILES["tools/phase.py"] = PHASE_CODE

AGENT_GUARD_CODE = r'''"""Claude Code PreToolUse guard: refuse shell commands that bypass the git hooks or the branch model.

Reads the hook payload (JSON) on stdin. Exit 2 blocks the command and shows the reason to the agent.
"""
import json
import re
import sys

import git_guard as guard

GIT = r'\bgit\b[^\n;&|]*'
RULES = (
    (r'--no-verify\b', 'never bypass git hooks (--no-verify).'),
    (GIT + r'\bcommit\b[^\n;&|]*\s-[A-Za-z]*n[A-Za-z]*(?=\s|$)', 'never bypass git hooks (git commit -n).'),
    (r'core\.hooksPath', 'do not change core.hooksPath; run python tools/runs.py setup.'),
    (GIT + r'\bupdate-ref\b', 'do not move branch refs directly.'),
    (GIT + r'\bpush\b[^\n;&|]*(?:\s--force(?:-with-lease)?\b|\s-f\b|\s\+\S)', 'no force push.'),
    (r'--allow-unrelated-histories\b', 'the main and runs branches never merge.'),
)
MERGE = re.compile(GIT + r'\bmerge(?![-\w])([^\n;&|]*)')
SWITCH = re.compile(GIT + r'\b(?:switch|checkout)\b([^\n;&|]*)')
CLEAN = re.compile(GIT + r'\bclean\b([^\n;&|]*)')

def blocked_reason(command, branch, protected, runs='runs'):
    """Return why the command is refused, or None."""
    for pattern, reason in RULES:
        if re.search(pattern, command):
            return reason
    for match in CLEAN.finditer(command):
        flags = ''.join(re.findall(r'(?:^|\s)-([A-Za-z]+)', match[1]))
        if flags.count('f') + match[1].count('--force') >= 2:
            return 'git clean with a double force deletes nested worktrees such as runs/.'
    if branch == runs:
        for match in SWITCH.finditer(command):
            if not re.search(r'(?:^|\s)--(?:\s|$)', match[1]):
                return f'the runs worktree stays on {runs}; do phase work with python tools/phase.py start <slug>.'
    if branch in protected:
        for match in MERGE.finditer(command):
            args = match[1]
            if re.search(r'--(?:squash|abort|continue|quit)\b', args):
                continue
            if '--ff-only' in args and 'phase/' not in args:
                continue
            return (f'{branch} accepts only squash merges; run python tools/phase.py finish "<summary>" '
                    '(or git pull --ff-only / --rebase to sync a remote).')
    return None

def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (payload.get('tool_input') or {}).get('command') or ''
    if 'git' not in command:
        return 0
    cwd = payload.get('cwd') or None
    try:
        reason = blocked_reason(command, guard.current_branch(cwd), guard.protected_branches(cwd),
                                guard.runs_branch(cwd))
    except OSError:
        reason = None
    if reason:
        print(f'Blocked by tools/agent_guard.py: {reason} See docs/work-modes.md.', file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'''

FILES["tools/agent_guard.py"] = AGENT_GUARD_CODE

RUNS_CODE = r'''"""Runtime records live on an orphan `runs` branch, checked out as the `runs/` worktree of the main worktree.

  python tools/runs.py setup                     idempotent: hooks, main branch, runs branch + worktree, push refspecs
  python tools/runs.py record <id> "<summary>"   stamp runs/<id>/run.json with the pipeline commit, commit on runs
  python tools/runs.py status                    show the runs worktree and unpushed records

The main branch never contains runtime records, and the two branches never share history.
"""
import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
import sys
from pathlib import Path

import git_guard as guard

RUN_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')
META = 'run.json'
SEED = {
    '.gitignore': ('# Runtime branch: commit metadata (run.json, manifests, logs, scripts), not large outputs.\n'
                   '*.mp4\n*.mov\n*.mkv\n*.webm\n*.wav\n*.mp3\n*.flac\n*.zip\n*.safetensors\n'),
    'README.md': ('# Runtime Records\n\nOne folder per run. From the main worktree, '
                  '`python tools/runs.py record <id> "<summary>"` stamps `<id>/run.json` with the pipeline commit '
                  'and commits it here.\n\nThis branch never merges with the main branch.\n'),
}

class RunsError(Exception):
    pass

def git(*args, cwd, data=None):
    # Bytes in and out: text-mode stdin turns LF into CRLF on Windows and corrupts mktree input.
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True,
                            input=data.encode('utf-8') if data is not None else None)
    out, err = (s.decode('utf-8', 'replace').strip() for s in (result.stdout, result.stderr))
    if result.returncode:
        raise RunsError(f'git {" ".join(args)} failed:\n{err or out}')
    return out

def try_git(*args, cwd):
    try:
        return git(*args, cwd=cwd)
    except RunsError:
        return None

def worktrees(cwd):
    """List of (path, branch); the first entry is the main worktree."""
    items = []
    for line in git('worktree', 'list', '--porcelain', cwd=cwd).splitlines():
        if line.startswith('worktree '):
            items.append([Path(line[9:]), ''])
        elif line.startswith('branch ') and items:
            items[-1][1] = line[7:].removeprefix('refs/heads/')
    return [tuple(item) for item in items]

def main_worktree(cwd):
    return worktrees(cwd)[0][0]

def runs_worktree(cwd):
    branch = guard.runs_branch(cwd)
    return next((path for path, name in worktrees(cwd) if name == branch), None)

def missing_refspecs(existing, branches):
    wanted = [f'refs/heads/{b}:refs/heads/{b}' for b in branches]
    return [spec for spec in wanted if spec not in existing]

def stamp(existing, run_id, summary, pipeline, dirty, now):
    """Merge runtime provenance into the run's metadata without dropping fields the pipeline wrote."""
    meta = dict(existing)
    meta.update({'run': run_id, 'summary': summary, 'pipeline': pipeline,
                 'pipeline_dirty': dirty, 'recorded_at': now})
    return meta

def create_orphan(main, branch):
    entries = []
    for name, text in SEED.items():
        oid = git('hash-object', '-w', '--stdin', cwd=main, data=text)
        entries.append(f'100644 blob {oid}\t{name}')
    tree = git('mktree', cwd=main, data='\n'.join(entries) + '\n')
    commit = git('commit-tree', tree, '-m', 'runs: initialize runtime records', cwd=main)
    git('branch', branch, commit, cwd=main)

def ensure_ignored(main):
    if try_git('check-ignore', '-q', f'{guard.RUNS_DIR}/probe', cwd=main) is not None:
        return False
    path = main / '.gitignore'
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    path.write_text(text + ('' if not text or text.endswith('\n') else '\n') + f'/{guard.RUNS_DIR}/\n',
                    encoding='utf-8', newline='\n')
    return True

def setup(cwd):
    main = main_worktree(cwd)
    git('config', '--local', 'core.hooksPath', (main / '.githooks').as_posix(), cwd=main)
    print(f'hooks: {main / ".githooks"}')
    main_branch = guard.config('harness.mainBranch', main) or guard.current_branch(main)
    if not main_branch:
        raise RunsError('main worktree is detached; check out the main branch first.')
    git('config', '--local', 'harness.mainBranch', main_branch, cwd=main)
    branch = guard.runs_branch(main)
    remote = 'origin' if 'origin' in (try_git('remote', cwd=main) or '').split() else ''
    if try_git('rev-parse', '-q', '--verify', f'refs/heads/{branch}', cwd=main) is None:
        if remote:
            try_git('fetch', remote, f'{branch}:refs/remotes/{remote}/{branch}', cwd=main)
        if remote and try_git('rev-parse', '-q', '--verify', f'refs/remotes/{remote}/{branch}', cwd=main):
            git('branch', '--track', branch, f'{remote}/{branch}', cwd=main)
            print(f'runs branch: tracking {remote}/{branch}')
        else:
            create_orphan(main, branch)
            print(f'runs branch: created orphan {branch}')
    if ensure_ignored(main):
        print(f'.gitignore: added /{guard.RUNS_DIR}/ (commit it in a phase)')
    target = main / guard.RUNS_DIR
    current = runs_worktree(main)
    if current is None:
        if target.exists() and any(target.iterdir()):
            raise RunsError(f'{target} exists and is not empty; move it away, then rerun setup.')
        git('worktree', 'add', str(target), branch, cwd=main)
        print(f'runs worktree: {target}')
    elif current.resolve() != target.resolve():
        print(f'runs worktree: {current} (expected {target}; tools look it up through git worktree list)')
    else:
        print(f'runs worktree: {target}')
    if remote:
        existing = (try_git('config', '--get-all', f'remote.{remote}.push', cwd=main) or '').split()
        for spec in missing_refspecs(existing, (main_branch, branch)):
            git('config', '--add', f'remote.{remote}.push', spec, cwd=main)
        print(f'push: git push sends {main_branch} and {branch} to {remote}')
    else:
        print('push: no origin remote yet; after adding it, rerun setup, then: '
              f'git push -u origin {main_branch} {branch}')

def record(run_id, summary, cwd):
    if not RUN_ID.match(run_id):
        raise RunsError('run id: letters, digits, dot, underscore or hyphen; at most 80 characters.')
    summary = ' '.join(summary.split())
    if not summary:
        raise RunsError('summary must not be empty.')
    main = main_worktree(cwd)
    runs = runs_worktree(main)
    if runs is None:
        raise RunsError('no runs worktree; run python tools/runs.py setup.')
    folder = runs / run_id
    if not folder.is_dir():
        raise RunsError(f'{folder} does not exist; the pipeline writes its outputs there first.')
    pipeline = git('rev-parse', 'HEAD', cwd=main) if guard.head_exists(main) else ''
    dirty = bool(git('status', '--porcelain', '--untracked-files=no', cwd=main))
    path = folder / META
    existing = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    path.write_text(json.dumps(stamp(existing, run_id, summary, pipeline, dirty, now), indent=2,
                               ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    git('add', '--', run_id, cwd=runs)
    git('commit', '-m', f'run({run_id}): {summary}', cwd=runs)
    print(f'recorded {run_id} on {guard.runs_branch(main)} (pipeline {pipeline[:10] or "none"}'
          f'{", dirty" if dirty else ""}); push with: git push')
    if dirty:
        print('warning: the main worktree has uncommitted changes, so the pipeline commit is not exact.')

def status(cwd):
    main = main_worktree(cwd)
    runs = runs_worktree(main)
    print(f'main: {guard.current_branch(main)} at {main}')
    if runs is None:
        print('runs: no worktree; run python tools/runs.py setup')
        return
    pending = len([l for l in git('status', '--porcelain', cwd=runs).splitlines() if l])
    ahead = try_git('rev-list', '--count', '@{upstream}..HEAD', cwd=runs)
    print(f'runs: {guard.runs_branch(main)} at {runs}; {pending} uncommitted paths; '
          f'{ahead + " unpushed commits" if ahead is not None else "no upstream yet"}')

def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('setup')
    rec = commands.add_parser('record')
    rec.add_argument('run_id')
    rec.add_argument('summary')
    commands.add_parser('status')
    args = parser.parse_args(argv)
    cwd = Path.cwd()
    try:
        if args.command == 'setup':
            setup(cwd)
        elif args.command == 'record':
            record(args.run_id, args.summary, cwd)
        else:
            status(cwd)
    except RunsError as error:
        print(f'[runs] {error}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'''

FILES["tools/runs.py"] = RUNS_CODE

TEST_GIT_GUARD_CODE = r'''"""Workflow guard regression tests: main-branch rules, agent command guard, phase parsing, runs branch."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import agent_guard
import git_guard as guard
import phase
import runs

class MessageTest(unittest.TestCase):
    def test_phase_subject_passes(self):
        self.assertEqual(guard.message_errors('phase(3): add subtitle pipeline\n'), [])

    def test_other_subjects_fail(self):
        for text in ('run: produce episode\n', 'feat: add thing\n', 'phase(x): bad number\n'):
            self.assertTrue(guard.message_errors(text), text)

    def test_long_subject_fails(self):
        self.assertTrue(guard.message_errors('phase(1): ' + 'x' * 80))

    def test_body_must_stay_short(self):
        ok = 'phase(2): ship editor\n\nWhy one.\nWhy two.\n\nCo-Authored-By: A <a@b.c>\n'
        self.assertEqual(guard.message_errors(ok), [])
        squash_log = 'phase(2): ship editor\n\n' + ''.join(f'    wip {i}\n' for i in range(9))
        self.assertTrue(any('concise' in e for e in guard.message_errors(squash_log)))

    def test_body_needs_blank_line_and_comments_ignored(self):
        self.assertTrue(guard.message_errors('phase(1): x\nbody\n'))
        self.assertEqual(guard.message_errors('# help\nphase(1): x\n# more\n'), [])

class PathTest(unittest.TestCase):
    def test_runs_paths(self):
        paths = ['runs', 'runs/ep12/run.json', 'src/core/a.py', 'runsheet.md', '']
        self.assertEqual(guard.runs_paths(paths), ['runs', 'runs/ep12/run.json'])

class AgentGuardTest(unittest.TestCase):
    PROTECTED = ('main',)

    def reason(self, command, branch='main'):
        return agent_guard.blocked_reason(command, branch, self.PROTECTED, 'runs')

    def test_hook_bypass_blocked(self):
        for command in ('git commit --no-verify -m x', 'git commit -nm x', 'git -c core.hooksPath=/dev/null commit -m x',
                        'git config core.hooksPath .githooks', 'git update-ref refs/heads/main abc',
                        'git push --force origin main', 'git merge --allow-unrelated-histories runs'):
            self.assertTrue(self.reason(command), command)

    def test_merge_on_main(self):
        self.assertTrue(self.reason('git merge phase/2-editor'))
        self.assertTrue(self.reason('git merge --ff-only phase/2-editor'))
        self.assertIsNone(self.reason('git merge --squash phase/2-editor'))
        self.assertIsNone(self.reason('git merge --ff-only origin/main'))
        self.assertIsNone(self.reason('git merge main', branch='phase/2-editor'))

    def test_runs_worktree_stays_on_runs(self):
        self.assertTrue(self.reason('git switch main', branch='runs'))
        self.assertTrue(self.reason('git checkout main', branch='runs'))
        self.assertIsNone(self.reason('git checkout -- ep1/run.json', branch='runs'))
        self.assertIsNone(self.reason('git switch phase/2-x', branch='main'))

    def test_double_force_clean_blocked(self):
        self.assertTrue(self.reason('git clean -ffdx'))
        self.assertTrue(self.reason('git clean -f -f -d'))
        self.assertIsNone(self.reason('git clean -fdx'))

    def test_normal_commands_pass(self):
        for command in ('git commit -m "phase(1): x"', 'git merge-base --is-ancestor main phase/2-x',
                        'git push origin main', 'git status'):
            self.assertIsNone(self.reason(command), command)

class PhaseParsingTest(unittest.TestCase):
    def test_current_phase(self):
        self.assertEqual(phase.current_phase('# R\n\n## Current State\n\nCurrent Phase: 4\n'), 4)
        with self.assertRaises(phase.PhaseError):
            phase.current_phase('no marker')

    def test_names(self):
        self.assertTrue(phase.SLUG.match('subtitle-pipeline'))
        self.assertFalse(phase.SLUG.match('Bad Slug'))
        self.assertEqual(phase.BRANCH.match('phase/12-subtitle-pipeline')[1], '12')

class RunsUnitTest(unittest.TestCase):
    def test_stamp_keeps_pipeline_fields(self):
        meta = runs.stamp({'duration': 61, 'run': 'old'}, 'ep1', 'accepted', 'abc', False, 'T')
        self.assertEqual(meta, {'duration': 61, 'run': 'ep1', 'summary': 'accepted', 'pipeline': 'abc',
                                'pipeline_dirty': False, 'recorded_at': 'T'})

    def test_missing_refspecs(self):
        existing = ['refs/heads/main:refs/heads/main']
        self.assertEqual(runs.missing_refspecs(existing, ('main', 'runs')), ['refs/heads/runs:refs/heads/runs'])

    def test_run_id(self):
        self.assertTrue(runs.RUN_ID.match('0047_the-raven'))
        self.assertFalse(runs.RUN_ID.match('../escape'))

@unittest.skipUnless(shutil.which('git'), 'git not installed')
class RunsIntegrationTest(unittest.TestCase):
    """setup creates an orphan runs worktree; record commits there and leaves the main branch untouched."""

    def git(self, *args, cwd=None):
        return subprocess.run(['git', *args], cwd=cwd or self.main, capture_output=True, text=True,
                              check=True).stdout.strip()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.main = Path(self.tmp.name, 'repo')
        self.main.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'test')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'core.autocrlf', 'false')

    def tearDown(self):
        subprocess.run(['git', 'worktree', 'remove', '--force', 'runs'], cwd=self.main, capture_output=True)
        self.tmp.cleanup()

    def test_setup_and_record(self):
        runs.setup(self.main)
        runs.setup(self.main)  # idempotent
        self.assertEqual(self.git('config', 'harness.mainBranch'), 'main')
        worktree = self.main / 'runs'
        self.assertEqual(self.git('branch', '--show-current', cwd=worktree), 'runs')
        self.git('add', '.gitignore')
        self.git('commit', '-qm', 'phase(1): scaffold')
        (worktree / 'ep1').mkdir()
        (worktree / 'ep1' / 'run.json').write_text('{"duration": 61}\n', encoding='utf-8')
        (worktree / 'ep1' / 'video.mp4').write_bytes(b'media')
        runs.record('ep1', 'accept episode one', self.main)
        meta = json.loads(self.git('show', 'runs:ep1/run.json'))
        self.assertEqual(meta['pipeline'], self.git('rev-parse', 'main'))
        self.assertEqual(meta['duration'], 61)
        self.assertEqual(self.git('log', '-1', '--format=%s', 'runs', '--'), 'run(ep1): accept episode one')
        self.assertNotIn('ep1/video.mp4', self.git('ls-tree', '-r', '--name-only', 'runs'))
        self.assertEqual(self.git('log', '--format=%s', 'main', '--'), 'phase(1): scaffold')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertIsNone(guard.git('merge-base', 'main', 'runs', cwd=self.main, check=False))

if __name__ == '__main__':
    unittest.main()
'''

FILES["tools/test_git_guard.py"] = TEST_GIT_GUARD_CODE

def bootstrap():
    parser = argparse.ArgumentParser(description="Bootstrap Agent Harness")
    parser.add_argument("project_name", nargs="?", default="MyProject", help="Project name")
    args = parser.parse_args()

    root = Path.cwd()
    print(f"[INFO] Initializing Universal Agent Harness for {args.project_name} in {root}...")

    for rel_path, content in FILES.items():
        file_path = root / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8", newline="\n")
            print(f"  + [Created] {rel_path}")
        else:
            print(f"  . [Exists - Skipped] {rel_path}")

    # Set execute permissions for git hooks on Unix systems
    if os.name != 'nt':
        for hook_file in (root / ".githooks").glob("*"):
            try:
                hook_file.chmod(0o755)
            except Exception:
                pass

    # Inside a Git repository: exempt existing history, then hooks, main branch, runs branch + worktree
    if (root / ".git").exists():
        head = subprocess.run(["git", "rev-parse", "-q", "--verify", "HEAD"], cwd=root,
                              capture_output=True, text=True).stdout.strip()
        baseline = subprocess.run(["git", "config", "--get", "harness.baseline"], cwd=root,
                                  capture_output=True, text=True).stdout.strip()
        if head and not baseline:
            subprocess.run(["git", "config", "--local", "harness.baseline", head], cwd=root, check=True)
            print(f"  ✓ [GIT] Existing history before {head[:10]} is exempt from the pre-push rules")
        print("  → [GIT] python tools/runs.py setup")
        res = subprocess.run([sys.executable, "tools/runs.py", "setup"], cwd=root)
        if res.returncode:
            print("\n[WARN] Git workflow setup failed. Fix the problem above, then run: python tools/runs.py setup")
            sys.exit(res.returncode)
    else:
        print("  ! [NOTE] Directory is not a Git repo yet. After `git init`, run: python tools/runs.py setup")

    # Run initial verification
    print("\n[INFO] Running initial health and boundary verification...")
    res = subprocess.run([sys.executable, "tools/verify.py"], cwd=root)
    if res.returncode == 0:
        print(f"\n[SUCCESS] Congratulations! {args.project_name} successfully initialized with Universal Agent Harness!")
    else:
        print("\n[WARN] Initial validation failed. Please check the logs above.")
        sys.exit(res.returncode)

if __name__ == "__main__":
    bootstrap()
