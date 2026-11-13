# Documentation Policy

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
- Pre-commit (automatic): `python tools/check_docs.py --staged`, then `python tools/doc_review.py`.
- `doc_review.py` sends only staged changes to these documents to a small model, judged against this Current State at HEAD.
- Fresh clone: `python tools/runs.py setup`

## Records

