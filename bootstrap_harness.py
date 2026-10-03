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

Read ONLY this file, [Architecture](ARCHITECTURE.md), and the active plan in `docs/exec-plans/active/`. Consult the [Roadmap](docs/exec-plans/roadmap.md) and the [Index](docs/README.md) on demand; NEVER load documents in bulk.

## Working Rules

- Use English for user communication, code, commands, and documentation.
- The user decides product direction; ask when uncertain instead of assuming competitor behavior or making guesses. Confirmed instructions override historical records.
- Strict architectural boundaries: `src/core` is pure business logic and must NOT depend on platform APIs, UI, networking, or external I/O.
- UI must use responsive layout containers; NEVER hardcode screen positions or offsets. Presentation only projects state snapshots; animations/rendering must NOT trigger gameplay or state side-effects.
- Decisions, constraints, and evidence are preserved in the repository. Unverified features must never be marked as completed.

## Planning

- The [Roadmap](docs/exec-plans/roadmap.md) is the only project-wide plan: goal, `Current Phase: <N>`, ordered phases with status, approved direction. Only the user approves changes.
- `docs/exec-plans/active/` holds at most one plan: the current roadmap phase, detailed enough for `/goal` to run it unattended. It opens with `Status:`, `Next Step:`, `Blockers:`, `Roadmap: Phase <N>`, then tasks, acceptance criteria (commands and thresholds) and the attempt budget. Long specs go in linked design docs; tasks and acceptance stay in the plan.
- Phase handoff, in one commit: verify acceptance; move the plan with its evidence to `completed/`; update roadmap phase status and `Current Phase:`; write the next phase in full into `active/`, or `Status: awaiting user` with the open decisions if its direction is not approved.
- Precedence: explicit user instruction > roadmap > active plan. If the plan and the roadmap disagree, stop and ask.
- User-paused plans go to `paused/`; never resume them without authorization.

## Autonomous Mode (/goal, unattended tasks, batch runs)

Under `/goal` or any multi-step goal without continuous human approval:

1. **Continuous Execution**: Do not halt for routine "what next" questions; keep executing toward the objective.
2. **Exploration Budget**: At most 3 distinct approaches/iterations unless specified. Stop and report if all 3 fail.
3. **Pre-Registration**: Record each approach and its acceptance criteria in the active plan before substantive code changes.
4. **Hard Permission Gates**: Halt and ask the user before:
   - Modifying the goal, the roadmap, or weakening acceptance criteria/test assertions.
   - Modifying core architectural invariants, schemas, or dependency rules in `ARCHITECTURE.md`.
   - Deleting past test logs, metrics, or archival evidence.
   - Exceeding the budgeted iteration limit.
5. **Turn Heartbeat**: End every turn with `LOOP: attempt <k>/<N> | <current_state> | <verification_metric_or_blocker>`

## Documentation Laws

- In `docs/` (excluding `archive/`), each Markdown file has exactly one title, `## Current State`, and `## Records`. Use level 3+ headings for sub-sections.
- Current State: maximum 2,000 characters, current facts only, rewritten in place. Remove superseded facts. Single source of truth.
- Records: `### YYYY-MM-DD Title`, newest first, at most 5 entries. `--fix` rotates older entries to `docs/archive/`.
- AGENTS.md <= 4,000 chars, ARCHITECTURE.md <= 6,000 chars; required reading (AGENTS + ARCHITECTURE + active plan) <= 10,000 chars.
- `python tools/check_docs.py` must pass before commit; it also enforces the Planning rules. The pre-commit hook checks the staged index; re-stage after fixing.
- Run `git config --local core.hooksPath .githooks` on every fresh clone.

## Commands

- Full verification: `python tools/verify.py`
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
            "command": "grep -q \\"git commit\\" || exit 0; cd \\"$CLAUDE_PROJECT_DIR\\" && python tools/check_architecture.py >&2 || exit 2",
            "timeout": 60,
            "statusMessage": "Architecture gate before commit"
          }
        ]
      }
    ]
  }
}
""",

    ".githooks/pre-commit": """#!/bin/sh
set -eu
cd "$(git rev-parse --show-toplevel)"
python tools/check_docs.py --staged || {
    echo "Docs check failed. Fix current state manually or run: python tools/check_docs.py --fix; review and git add the results." >&2
    exit 1
}
python tools/check_architecture.py || {
    echo "Architecture check failed. Fix boundary violations before committing." >&2
    exit 1
}
""",

    "docs/README.md": """# Documentation Index

## Current State

Consult on-demand; do not load documents in bulk.

| Category | Entry Point |
| --- | --- |
| Roadmap (project plan) | [Roadmap](exec-plans/roadmap.md) |
| Plans | [Plan Index](exec-plans/README.md) |
| Documentation Policy | [Documentation Policy](documentation-policy.md) |
| Test Responsibilities | [Test Responsibilities](../tests/README.md) |

Documentation follows the "Current State / Records" duality; historical records archive in `docs/archive/`.

## Records

""",

    "docs/documentation-policy.md": """# Documentation Policy

## Current State

### Format and Rules

- Strictly adhere to [AGENTS Documentation Laws](../AGENTS.md).
- Fixed two-section structure: `# Title`, `## Current State`, `## Records`.
- Current State: maximum 2,000 characters, rewritten in-place.
- Records: maximum 5 entries, newest first (`### YYYY-MM-DD Title`).

### Usage

```bash
# Check current document formatting and limits
python tools/check_docs.py

# Automatically rotate 6th+ record entries to docs/archive/ and update links
python tools/check_docs.py --fix

# Validate Git index (called automatically by pre-commit hook)
python tools/check_docs.py --staged

# Configure local Git hook path
git config --local core.hooksPath .githooks
```

## Records

""",

    "docs/exec-plans/README.md": """# Plans and Tasks

## Current State

- [Roadmap](roadmap.md): the only project-wide plan (goal, ordered phases, approved direction).
- `active/`: at most one plan, for the roadmap's `Current Phase: <N>`; the roadmap's Phase <N> line links it. Opens with `Status:`, `Next Step:`, `Blockers:`, `Roadmap: Phase <N>`; holds tasks, acceptance criteria and budget.
- `completed/`: finished phases with their evidence.
- `paused/`: explicitly postponed by the user; never resume without authorization.
- Rules live in [AGENTS](../../AGENTS.md) (Planning); `tools/check_docs.py` enforces them.

## Records

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
- Planning governance defined in [AGENTS](../../AGENTS.md).

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

1. **Architecture (`tools/check_architecture.py`)**: Static verification of core purity, forbidden dependencies, and UI layout constraints.
2. **Documentation Guard (`tools/test_check_docs.py`)**: Ensures documentation parser and archive rotation continue to work.
3. **Unit & Integration Tests**: Verify `src/core/` algorithms, state transitions, and edge cases.

Run all checks via `python tools/verify.py`.
""",

    "tools/check_architecture.py": """\"\"\"Executable architectural boundary checks.\"\"\"
import re
import sys
from pathlib import Path
from check_docs import check_docs

ROOT = Path(__file__).resolve().parents[1]

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_checks():
    errors = check_docs(ROOT)
    
    # Rule 1: Ensure Core layer remains pure (no I/O, UI, OS, or Network dependencies)
    core_dir = ROOT / 'src/core'
    if core_dir.exists():
        for file in core_dir.rglob('*.*'):
            if file.suffix in ['.py', '.js', '.ts', '.gd', '.go', '.rs']:
                text = file.read_text(encoding='utf-8')
                for forbidden in ['fetch(', 'axios', 'requests.', 'http.', 'socket', 'localStorage', 'window.']:
                    if forbidden in text:
                        errors.append(f"{file.relative_to(ROOT)}: Core layer must not import external I/O or view dependency '{forbidden}'")
                        
    # Rule 2: Ensure UI uses responsive containers (no hardcoded absolute positions)
    ui_dir = ROOT / 'src/ui'
    if ui_dir.exists():
        for file in ui_dir.rglob('*.*'):
            if file.suffix in ['.py', '.js', '.ts', '.gd']:
                text = file.read_text(encoding='utf-8')
                if re.search(r'position:\\s*absolute|offset_[a-z]+\\s*=', text):
                    errors.append(f"{file.relative_to(ROOT)}: UI must be managed by layout containers; do not hardcode screen coordinates.")

    if errors:
        print("\\n".join(errors), file=sys.stderr)
        return 1
    print("architecture OK")
    return 0

if __name__ == '__main__':
    sys.exit(run_checks())
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
    # 1. Architectural boundary check
    run_command([sys.executable, "tools/check_architecture.py"], "Architecture boundary check")
    # 2. Documentation guard regression test
    run_command([sys.executable, "tools/test_check_docs.py"], "Doc guard regression test")
    # 3. Domain unit tests (hook up your pytest / npm test / cargo test here)
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
STATE_LIMIT = 2000
MAX_LOG = 5
MANIFEST = 'docs/references/workflow-preservation.json'
ROADMAP = 'docs/exec-plans/roadmap.md'
ACTIVE_DIR = 'docs/exec-plans/active/'

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
    for number, line in enumerate(texts.get('ARCHITECTURE.md', '').splitlines(), 1):
        if len(line) > 200:
            errors.append(f'ARCHITECTURE.md:{number}: split constraint to <=200 characters.')
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
        if not state or len(state) > STATE_LIMIT:
            errors.append(f'{name}: current state must be 1..{STATE_LIMIT} characters (got {len(state)}); rewrite in place.')
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

    # Set execute permissions for pre-commit hook on Unix systems
    hook_file = root / ".githooks" / "pre-commit"
    if hook_file.exists() and os.name != 'nt':
        try:
            hook_file.chmod(0o755)
        except Exception:
            pass

    # Configure git hooksPath if inside a Git repository
    if (root / ".git").exists():
        try:
            subprocess.run(["git", "config", "--local", "core.hooksPath", ".githooks"], check=True, capture_output=True)
            print("  ✓ [GIT] Successfully configured hooks path: .githooks")
        except Exception as e:
            print(f"  ! [GIT] Hook configuration hint: {e}")
    else:
        print("  ! [NOTE] Directory is not a Git repo yet. After `git init`, run: git config --local core.hooksPath .githooks")

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
