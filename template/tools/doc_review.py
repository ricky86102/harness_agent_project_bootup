"""LLM cleanliness review of staged governed-document changes (run by the pre-commit hook).

Nothing here is hard-coded policy:
  - scope: check_docs.is_document() (AGENTS.md, ARCHITECTURE.md, docs/ except archive/);
  - rubric: Current State of docs/documentation-policy.md at HEAD (the pre-change rules);
  - owners: the AGENTS.md reading-trigger table at HEAD plus check_docs.POLICIES;
  - doc_review_prompt.md holds only the frame: role, data boundaries, output shape.
The reviewer CLI runs in an empty temporary directory with no tools and no user or project
settings, so it sees only the staged document diff passed on stdin.

Engine: git config harness.reviewer (claude | codex), else the agent that is committing, else the
first CLI found. Models: harness.reviewerClaudeModel (default haiku), harness.reviewerCodexModel
(default gpt-6-luna). Reviewer outages warn and allow the commit unless harness.reviewStrict=true.
"""
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import check_docs as docs

FRAME = Path(__file__).with_name('doc_review_prompt.md')
POLICY = 'docs/documentation-policy.md'
MAX_DIFF = 30000
TIMEOUT = 240
CACHE = 'harness-doc-review.json'
CACHE_SIZE = 500
ENGINES = ('claude', 'codex')
DEFAULT_MODELS = {'claude': 'haiku', 'codex': 'gpt-6-luna'}
MODEL_KEYS = {'claude': 'harness.reviewerClaudeModel', 'codex': 'harness.reviewerCodexModel'}
SCHEMA = {
    'type': 'object',
    'properties': {
        'verdict': {'type': 'string', 'enum': ['pass', 'fail']},
        'issues': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'file': {'type': 'string'}, 'line': {'type': 'integer'},
                           'problem': {'type': 'string'}, 'fix': {'type': 'string'}},
            'required': ['file', 'line', 'problem', 'fix'],
            'additionalProperties': False,
        }},
    },
    'required': ['verdict', 'issues'],
    'additionalProperties': False,
}

class ReviewError(Exception):
    """The reviewer could not run or answer (CLI missing, timeout, unusable output)."""

def git(*args, cwd=None, check=True):
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True)
    if result.returncode:
        if check:
            raise ReviewError(f'git {" ".join(args)} failed: {result.stderr.decode("utf-8", "replace").strip()}')
        return None
    return result.stdout.decode('utf-8', 'replace')

def config(key, cwd=None):
    return (git('config', '--get', key, cwd=cwd, check=False) or '').strip()

def in_scope(path):
    return docs.is_document(path) and path != 'CLAUDE.md' and not path.startswith('docs/archive/')

def staged_scope(cwd=None):
    names = git('diff', '--cached', '--name-only', '--no-renames', '-z', cwd=cwd).split('\0')
    return sorted(name for name in names if name and in_scope(name))

def staged_diff(paths, cwd=None):
    return git('diff', '--cached', '--no-color', '--no-renames', '--unified=3', '--', *paths, cwd=cwd)

def committed_or_staged(path, cwd=None):
    """HEAD version (rules before this commit); the staged version only before the first commit."""
    return git('show', f'HEAD:{path}', cwd=cwd, check=False) or git('show', f':{path}', cwd=cwd, check=False) or ''

def rubric(cwd=None):
    state = docs.current_state(POLICY, committed_or_staged(POLICY, cwd).replace('\r\n', '\n'))
    if not state:
        raise ReviewError(f'{POLICY} has no readable Current State to use as the rubric.')
    return state

def owners(cwd=None):
    agents = committed_or_staged('AGENTS.md', cwd)
    table = [line for line in agents.splitlines() if line.startswith('|')]
    return '\n'.join(table + ['', 'Owning policies: ' + ', '.join(docs.POLICIES)])

def build_prompt(frame, rubric_text, owners_text, files, diff, nonce=None):
    nonce = nonce or secrets.token_hex(8)
    parts = (('RUBRIC', rubric_text), ('OWNERS', owners_text), ('FILES', '\n'.join(files)), ('DIFF', diff))
    sections = '\n\n'.join(f'<<<{name} {nonce}\n{body.strip()}\n{name} {nonce}>>>' for name, body in parts)
    return frame.replace('@@SECTIONS@@', sections)

def select_engine(env, configured, available):
    if configured in ENGINES:
        return configured
    if env.get('CLAUDECODE'):
        return 'claude'
    if any(key.startswith('CODEX_') for key in env):
        return 'codex'
    for engine in ENGINES:
        if available(engine):
            return engine
    raise ReviewError('no reviewer CLI found; install claude or codex, or set git config harness.reviewer.')

def command(engine, executable, model, schema_path, output_path):
    if engine == 'claude':
        return [executable, '-p', '--model', model, '--tools', '', '--setting-sources', '', '--strict-mcp-config',
                '--no-session-persistence', '--output-format', 'json']
    return [executable, 'exec', '-m', model, '-s', 'read-only', '--skip-git-repo-check', '--ephemeral',
            '--ignore-user-config', '--ignore-rules', '--color', 'never', '-c', 'model_reasoning_effort="low"',
            '--output-schema', str(schema_path), '-o', str(output_path), '-']

def extract_json(text):
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        raise ReviewError('reviewer reply contains no JSON object.')
    try:
        return json.loads(text[start:end + 1])
    except ValueError as error:
        raise ReviewError(f'reviewer reply is not valid JSON: {error}') from error

def parse(engine, stdout, output_path):
    if engine == 'codex':
        return extract_json(Path(output_path).read_text(encoding='utf-8') if Path(output_path).exists() else stdout)
    envelope = extract_json(stdout)
    if envelope.get('is_error'):
        raise ReviewError(f'claude: {envelope.get("result")}')
    payload = envelope.get('structured_output') or envelope.get('result') or ''
    return payload if isinstance(payload, dict) else extract_json(payload)

def validate(result, files):
    """Return reasons the reply is unusable; an unusable reply blocks the commit."""
    errors = []
    issues = result.get('issues')
    if result.get('verdict') not in ('pass', 'fail'):
        errors.append(f'invalid verdict {result.get("verdict")!r}')
    if not isinstance(issues, list) or not all(isinstance(i, dict) for i in issues):
        return errors + ['issues must be a list of objects']
    for issue in issues:
        if issue.get('file') not in files:
            errors.append(f'issue outside the reviewed files: {issue.get("file")!r}')
    if (result.get('verdict') == 'pass') != (not issues):
        errors.append('verdict must be "pass" exactly when there are no issues')
    return errors

def cache_keys(files, rubric_text, frame, cwd=None):
    salt = hashlib.sha256((rubric_text + '\0' + frame).encode('utf-8')).hexdigest()
    keys = {}
    for path in files:
        blob = (git('rev-parse', f':{path}', cwd=cwd, check=False) or 'deleted').strip()
        keys[path] = hashlib.sha256(f'{path}\0{blob}\0{salt}'.encode('utf-8')).hexdigest()
    return keys

def cache_path(cwd=None):
    return Path(cwd or '.', git('rev-parse', '--git-common-dir', cwd=cwd).strip(), CACHE)

def load_cache(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []

def review(cwd=None, runner=subprocess.run, env=None, which=shutil.which):
    """Return 0 to allow the commit, 1 to block it. Raises ReviewError when the reviewer cannot run."""
    env = dict(os.environ if env is None else env)
    files = staged_scope(cwd)
    if not files:
        print('doc review: no document changes')
        return 0
    frame = FRAME.read_text(encoding='utf-8')
    rubric_text = rubric(cwd)
    keys = cache_keys(files, rubric_text, frame, cwd)
    store = cache_path(cwd)
    approved = load_cache(store)
    if all(key in approved for key in keys.values()):
        print(f'doc review: already approved ({", ".join(files)})')
        return 0
    diff = staged_diff(files, cwd)
    if len(diff) > MAX_DIFF:
        print(f'[doc_review] document diff has {len(diff)} characters > {MAX_DIFF}; split the commit.', file=sys.stderr)
        return 1
    prompt = build_prompt(frame, rubric_text, owners(cwd), files, diff)
    engine = select_engine(env, config('harness.reviewer', cwd), which)
    executable = which(engine)
    if not executable:
        raise ReviewError(f'{engine} CLI not found.')
    model = config(MODEL_KEYS[engine], cwd) or DEFAULT_MODELS[engine]
    for key in [k for k in env if k.startswith('CLAUDECODE') or k == 'CLAUDE_CODE_ENTRYPOINT']:
        env.pop(key)  # a nested headless run must not look like the committing session
    print(f'doc review: {engine} ({model}) on {", ".join(files)}')
    with tempfile.TemporaryDirectory(prefix='doc-review-') as tmp:
        empty = Path(tmp, 'empty')
        empty.mkdir()
        schema_path, output_path = Path(tmp, 'schema.json'), Path(tmp, 'last-message.json')
        schema_path.write_text(json.dumps(SCHEMA), encoding='utf-8')
        try:
            proc = runner(command(engine, executable, model, schema_path, output_path), cwd=empty, env=env,
                          input=prompt.encode('utf-8'), capture_output=True, timeout=TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ReviewError(f'{engine} did not finish: {error}') from error
        stdout = proc.stdout.decode('utf-8', 'replace')
        if proc.returncode:
            detail = (proc.stderr.decode('utf-8', 'replace') or stdout).strip()
            try:
                detail = str(json.loads(stdout).get('result') or detail)  # claude reports errors in its JSON envelope
            except (ValueError, AttributeError):
                pass
            detail = detail[-400:]
            raise ReviewError(f'{engine} exited {proc.returncode}: {detail}')
        result = parse(engine, stdout, output_path)
    errors = validate(result, files)
    if errors:
        print('\n'.join(f'[doc_review] unusable reviewer reply: {e}' for e in errors), file=sys.stderr)
        return 1
    if result['verdict'] == 'fail':
        for issue in result['issues']:
            print(f'[doc_review] {issue["file"]}:{issue.get("line", "?")}: {issue["problem"]}\n'
                  f'             fix: {issue["fix"]}', file=sys.stderr)
        print('[doc_review] Fix in place (replace, do not append), stage, and commit again.', file=sys.stderr)
        return 1
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps((approved + list(keys.values()))[-CACHE_SIZE:]), encoding='utf-8')
    print('doc review: pass')
    return 0

def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8')
            except Exception:
                pass
    try:
        return review()
    except ReviewError as error:
        strict = config('harness.reviewStrict').lower() == 'true'
        print(f'[doc_review] reviewer unavailable: {error}', file=sys.stderr)
        print('[doc_review] ' + ('harness.reviewStrict=true: commit blocked.' if strict
                                 else 'commit allowed without review; set harness.reviewStrict=true to block.'),
              file=sys.stderr)
        return 1 if strict else 0

if __name__ == '__main__':
    raise SystemExit(main())
