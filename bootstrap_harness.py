"""
bootstrap_harness.py
Universal, vendor-agnostic bootstrap script for the "Agentic Harness" development architecture.
Supports Claude Code, OpenAI Codex, Cursor, GitHub Copilot, Windsurf, and Antigravity.

Copies every file under template/ (next to this script) into the current directory, then sets up
git hooks, the protected main branch and the runs worktree, and runs the initial verification.
A trailing `.tmpl` is stripped from template names: it keeps files such as AGENTS.md, CLAUDE.md and
.gitignore from acting on this toolkit repository itself.

Usage: python <toolkit>/bootstrap_harness.py [ProjectName]
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "template"
TEMPLATE_SUFFIX = ".tmpl"

# Windows console encoding compatibility
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def template_files(template_dir=TEMPLATE_DIR):
    """Map each generated path (POSIX, relative) to its template file."""
    files = {}
    for path in sorted(p for p in template_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(template_dir).as_posix()
        if "__pycache__/" in rel + "/" or rel.endswith((".pyc", ".pyo")):
            continue
        files[rel.removesuffix(TEMPLATE_SUFFIX)] = path
    return files


def bootstrap():
    parser = argparse.ArgumentParser(description="Bootstrap Agent Harness")
    parser.add_argument("project_name", nargs="?", default="MyProject", help="Project name")
    args = parser.parse_args()

    if not TEMPLATE_DIR.is_dir():
        sys.exit(f"[ERROR] Template directory not found: {TEMPLATE_DIR}. Run this script from the toolkit checkout.")

    root = Path.cwd()
    print(f"[INFO] Initializing Universal Agent Harness for {args.project_name} in {root}...")

    for rel_path, source in template_files().items():
        file_path = root / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            # Text mode normalizes CRLF checkouts; generated files always use LF.
            content = source.read_text(encoding="utf-8")
            file_path.write_text(content, encoding="utf-8", newline="\n")
            print(f"  + [Created] {rel_path}")
        else:
            print(f"  . [Exists - Skipped] {rel_path}")

    # Set execute permissions for git hooks on Unix systems
    if os.name != "nt":
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
