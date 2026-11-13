"""Git hook entrypoint for the Phase / Runtime workflow (owner: docs/work-modes.md).

Hooks live in the main worktree (core.hooksPath is absolute, set by tools/runs.py setup), so they
also run in phase worktrees and in the runs worktree.

Main branch (git config harness.mainBranch):
  - pre-commit: only a phase squash merge in progress (or the first commit); then docs and architecture checks;
  - commit-msg: "phase(<N>): <summary>", concise;
  - pre-merge-commit: refuse merge commits (squash only).
Runs branch (git config harness.runsBranch, default runs): runtime records, free-form commits.
Every branch except runs: never stage the runs/ worktree path; staged document changes pass
tools/doc_review.py (LLM cleanliness review).
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

def review_docs():
    """LLM cleanliness review of staged document changes (tools/doc_review.py in this worktree)."""
    top = git('rev-parse', '--show-toplevel')
    script = Path(top, 'tools', 'doc_review.py')
    if not script.exists():
        return 0
    if subprocess.run([sys.executable, str(script)], cwd=top).returncode:
        return fail(['document review failed'], 'Fix the reported issues in place, stage them, and commit again.')
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
        return review_docs()  # phase branches commit freely, but document changes are still reviewed
    if not head_exists():
        return run_checks()  # the first commit is the generated scaffold; its documents ship pre-reviewed
    if git_state('MERGE_HEAD'):
        return fail([f'merge commit on {branch}'], 'Main accepts only squash merges: python tools/phase.py finish "<summary>"')
    if not git_state('SQUASH_MSG'):
        return fail([f'direct commit on {branch}'],
                    'Main receives only phase squash commits. Phase work: python tools/phase.py start <slug>. '
                    'Runtime records: python tools/runs.py record <id> "<summary>".')
    return run_checks() or review_docs()

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
