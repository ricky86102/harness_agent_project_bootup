# Test Responsibilities

Tests are partitioned strictly by responsibility to avoid redundant coverage:

1. **Architecture (`tools/check_architecture.py`, tested by `tools/test_check_architecture.py`)**: Comment- and string-aware verification of core purity, forbidden dependencies, and UI layout constraints.
2. **Documentation Guard (`tools/test_check_docs.py`)**: Ensures documentation parser, planning rules and archive rotation continue to work.
3. **Workflow Guard (`tools/test_git_guard.py`)**: Main-branch commit rules, the agent command guard, and phase parsing.
4. **Document Review (`tools/test_doc_review.py`)**: Reviewer scope, prompt assembly, reply validation and caching, with a fake CLI.
5. **Unit & Integration Tests**: Verify `src/core/` algorithms, state transitions, and edge cases.

Run all checks via `python tools/verify.py`.
