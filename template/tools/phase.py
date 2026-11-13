"""Phase workflow: one git worktree per roadmap phase, squash-merged to the main branch as one commit.

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
