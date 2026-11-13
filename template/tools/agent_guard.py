"""Claude Code PreToolUse guard: refuse shell commands that bypass the git hooks or the branch model.

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
