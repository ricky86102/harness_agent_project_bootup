"""Runtime records live on an orphan `runs` branch, checked out as the `runs/` worktree of the main worktree.

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
