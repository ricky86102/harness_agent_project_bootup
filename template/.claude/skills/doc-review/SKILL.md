---
name: doc-review
description: Review staged documentation changes (AGENTS.md, ARCHITECTURE.md, docs/) for cleanliness before committing. Use before git commit when such files are staged, or after the pre-commit document review failed.
---

# Document Review

1. Stage the document changes.
2. Run `python tools/doc_review.py`. It sends only the staged document diff to a small model and judges it against `docs/documentation-policy.md` at HEAD.
3. For each reported issue, fix the text in place: replace or delete, never append a correction.
4. Stage the fixes and rerun until it prints `doc review: pass`. The pre-commit hook runs the same review.

Never change `harness.review*` git settings and never bypass the hook.
