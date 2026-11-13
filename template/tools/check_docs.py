"""Enforce bounded current docs; rotate history explicitly, check Git's index in hooks."""
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
STATE_LIMIT = 2000          # roadmap, active plan, index and other docs
POLICY_STATE_LIMIT = 3000   # owning policies: read only when their trigger fires
MAX_LOG = 5
LINE_LIMIT = 200            # one fact per line; fenced code blocks are exempt
DUPLICATE_MIN = 80          # normalized lines this long may appear in one document only
FILLER = ('please note', 'note that', 'it is important', 'it should be noted', 'in order to',
          'make sure to', 'basically', 'as mentioned', 'as noted above', 'keep in mind', 'feel free',
          'needless to say', 'in other words', 'it is worth noting')
FILLER_RE = re.compile(r'\b(?:' + '|'.join(re.escape(f) for f in FILLER) + r')\b', re.I)
MANIFEST = 'docs/references/workflow-preservation.json'
ROADMAP = 'docs/exec-plans/roadmap.md'
ACTIVE_DIR = 'docs/exec-plans/active/'
POLICIES = ('docs/exec-plans/README.md', 'docs/documentation-policy.md', 'docs/autonomous-mode.md',
            'docs/work-modes.md')

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
    errors += check_writing(texts)
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
        limit = POLICY_STATE_LIMIT if name in POLICIES else STATE_LIMIT
        if not state or len(state) > limit:
            errors.append(f'{name}: current state must be 1..{limit} characters (got {len(state)}); rewrite in place.')
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
    errors += check_routes(texts)
    return errors

def prose_lines(text):
    """Yield (number, line) outside fenced code blocks."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not line[marker.end():].strip():
                fence = None
        elif marker:
            fence = marker[1]
        else:
            yield number, line

def check_writing(texts):
    """Terse writing: one fact per line, no filler phrases, each long rule stated in one document only."""
    errors, seen = [], {}
    for name in sorted(texts):
        if not is_document(name) or name == 'CLAUDE.md' or name.startswith('docs/archive/'):
            continue
        for number, line in prose_lines(texts[name]):
            if len(line) > LINE_LIMIT:
                errors.append(f'{name}:{number}: line has {len(line)} characters > {LINE_LIMIT}; one fact per line.')
            filler = FILLER_RE.search(re.sub(r'`[^`]*`', '', line))
            if filler:
                errors.append(f'{name}:{number}: filler phrase "{filler[0]}"; state the rule directly.')
            key = re.sub(r'\s+', ' ', re.sub(r'^\s*(?:[-*+]|\d+\.)\s+', '', line)).strip().lower()
            if len(key) < DUPLICATE_MIN:
                continue
            if key in seen and seen[key][0] != name:
                errors.append(f'{name}:{number}: repeats {seen[key][0]}:{seen[key][1]}; keep the rule in its owner and link to it.')
            seen.setdefault(key, (name, number))
    return errors

def check_routes(texts):
    """AGENTS.md is a map: every owning policy must exist and be routed from it."""
    errors, routes = [], links_in('AGENTS.md', texts.get('AGENTS.md', ''))
    for policy in POLICIES:
        if policy not in texts:
            errors.append(f'{policy}: required policy document missing.')
        elif policy not in routes:
            errors.append(f'AGENTS.md: Required Reading must route to {policy}.')
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
