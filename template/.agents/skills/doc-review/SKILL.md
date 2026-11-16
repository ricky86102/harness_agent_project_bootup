---
name: doc-review
description: Review staged AGENTS.md, ARCHITECTURE.md and docs/ changes before a requested commit, or diagnose a failed pre-commit document review.
---

# Document Review

Run from the generated repository root.

1. Stage only the documentation changes intended for the requested commit; preserve unrelated staged work.
2. Run `python tools/doc_review.py`; it reviews staged documentation against `docs/documentation-policy.md` at HEAD.
3. Fix reported issues in place, stage those fixes, and rerun within the task's attempt budget.
4. Distinguish `pass` or `already approved` from an outage warning; a warning is not a completed review.

The pre-commit hook repeats this check. Do not change `harness.review*`, bypass hooks, or commit unless the task authorizes it.
