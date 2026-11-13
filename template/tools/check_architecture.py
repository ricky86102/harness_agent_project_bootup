"""Executable architectural boundary checks.

Comments and string literals are ignored, so prose that mentions `http.` or
`window.` does not fail the build. Python is checked through its AST; other
languages through a comment/string-aware scanner. Documentation checks live in
check_docs.py and run separately (verify.py, pre-commit).
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = 'src/core'
UI_DIR = 'src/ui'

# Core is pure deterministic logic: no file system, process, OS, network, persistence or UI dependencies.
PY_FORBIDDEN_MODULES = {
    'os', 'shutil', 'pathlib', 'glob', 'tempfile', 'subprocess', 'multiprocessing', 'socket', 'ssl',
    'select', 'http', 'urllib', 'requests', 'httpx', 'aiohttp', 'websockets', 'sqlite3', 'pickle',
    'shelve', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'pygame', 'kivy', 'flask', 'django',
    'fastapi',
}
PY_FORBIDDEN_CALLS = {'open', 'input', '__import__'}
JS_FORBIDDEN_MODULES = {
    'fs', 'fs/promises', 'http', 'https', 'http2', 'net', 'tls', 'dgram', 'child_process', 'os',
    'worker_threads', 'axios', 'node-fetch', 'got', 'ws', 'react-dom', 'electron',
}
JS_FORBIDDEN_GLOBALS = {
    'fetch', 'XMLHttpRequest', 'WebSocket', 'EventSource', 'localStorage', 'sessionStorage',
    'indexedDB', 'document', 'window', 'navigator', 'process',
}
GO_FORBIDDEN_IMPORTS = {'os', 'net', 'syscall', 'io/ioutil', 'database/sql'}
RS_FORBIDDEN = r'\b(?:std::(?:fs|net|process|env)|tokio::(?:fs|net|process)|reqwest|hyper|ureq)\b'
GD_FORBIDDEN = (r'(?<![\w.])(?:FileAccess|DirAccess|HTTPRequest|HTTPClient|OS|Input|ResourceLoader|'
                r'ResourceSaver|JavaScriptBridge)\b|\bget_(?:tree|node)\s*\(')
UI_FORBIDDEN = (r'position\s*:\s*[\'"]?\s*absolute\b|\boffset_(?:left|right|top|bottom)\s*=|'
                r'\.place\(\s*x\s*=')

C_STYLE = {'line': ('//',), 'block': (('/*', '*/'),)}
LANGS = {
    '.py': {'line': ('#',), 'block': (), 'quotes': '\'"'},
    '.gd': {'line': ('#',), 'block': (), 'quotes': '\'"'},
    '.js': {**C_STYLE, 'quotes': '\'"`'},
    '.jsx': {**C_STYLE, 'quotes': '\'"`'},
    '.mjs': {**C_STYLE, 'quotes': '\'"`'},
    '.cjs': {**C_STYLE, 'quotes': '\'"`'},
    '.ts': {**C_STYLE, 'quotes': '\'"`'},
    '.tsx': {**C_STYLE, 'quotes': '\'"`'},
    '.vue': {'line': ('//',), 'block': (('/*', '*/'), ('<!--', '-->')), 'quotes': '\'"`'},
    '.svelte': {'line': ('//',), 'block': (('/*', '*/'), ('<!--', '-->')), 'quotes': '\'"`'},
    '.go': {**C_STYLE, 'quotes': '"`\''},
    '.rs': {**C_STYLE, 'quotes': '"'},
    '.css': {'line': (), 'block': (('/*', '*/'),), 'quotes': '\'"'},
    '.scss': {**C_STYLE, 'quotes': '\'"'},
}
JS_LIKE = {'.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.vue', '.svelte'}

def blank(segment):
    return re.sub(r'[^\n]', ' ', segment)

def strip_source(text, line=(), block=(), quotes=''):
    """Return (no_comments, code_only). Both keep offsets and newlines; code_only also blanks strings."""
    keep, code, i, n = [], [], 0, len(text)
    while i < n:
        opener = next((c for c in line if text.startswith(c, i)), None)
        if opener:
            end = text.find('\n', i)
            end = n if end < 0 else end
            keep.append(blank(text[i:end])); code.append(blank(text[i:end])); i = end
            continue
        pair = next((b for b in block if text.startswith(b[0], i)), None)
        if pair:
            end = text.find(pair[1], i + len(pair[0]))
            end = n if end < 0 else end + len(pair[1])
            keep.append(blank(text[i:end])); code.append(blank(text[i:end])); i = end
            continue
        if text[i] in quotes:
            quote, j = text[i], i + 1
            while j < n and text[j] != quote:
                j += 2 if text[j] == '\\' else 1
            end = min(j + 1, n)
            keep.append(text[i:end]); code.append(blank(text[i:end])); i = end
            continue
        keep.append(text[i]); code.append(text[i]); i += 1
    return ''.join(keep), ''.join(code)

def line_of(text, offset):
    return text.count('\n', 0, offset) + 1

def py_core_violations(text):
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return [(error.lineno or 1, f'cannot parse Python: {error.msg}')]
    found = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id in PY_FORBIDDEN_CALLS):
            found.append((node.lineno, f'forbidden call {node.func.id}()'))
        for name in names:
            if name.split('.')[0] in PY_FORBIDDEN_MODULES:
                found.append((node.lineno, f'forbidden import {name}'))
    return found

def js_module_root(spec):
    spec = spec.removeprefix('node:')
    if spec in JS_FORBIDDEN_MODULES:
        return spec
    parts = spec.split('/')
    return '/'.join(parts[:2]) if spec.startswith('@') else parts[0]

def core_violations(suffix, text):
    """List (line, message) for impure dependencies in a core source file."""
    if suffix == '.py':
        return py_core_violations(text)
    if suffix not in LANGS:
        return []
    no_comments, code = strip_source(text, **LANGS[suffix])
    found = []
    if suffix in JS_LIKE:
        imports = (r'\bfrom\s*([\'"])(.+?)\1|\bimport\s*\(?\s*([\'"])(.+?)\3|\brequire\s*\(\s*([\'"])(.+?)\5')
        for match in re.finditer(imports, no_comments):
            if code[match.start()] == ' ':
                continue  # the keyword itself sits inside a string literal
            spec = match[2] or match[4] or match[6]
            if js_module_root(spec) in JS_FORBIDDEN_MODULES:
                found.append((line_of(text, match.start()), f'forbidden import {spec}'))
        globals_ = '|'.join(sorted(JS_FORBIDDEN_GLOBALS))
        for match in re.finditer(rf'(?<![\w$.])({globals_})(?![\w$])', code):
            found.append((line_of(text, match.start()), f'forbidden global {match[1]}'))
    elif suffix == '.go':
        specs = []
        for match in re.finditer(r'\bimport\s*\(([^)]*)\)', no_comments):
            specs += [(match.start(), s) for s in re.findall(r'"([^"]+)"', match[1])]
        specs += [(m.start(), m[1]) for m in re.finditer(r'\bimport\s+(?:\w+\s+)?"([^"]+)"', no_comments)]
        for offset, spec in specs:
            if any(spec == bad or spec.startswith(bad + '/') for bad in GO_FORBIDDEN_IMPORTS):
                found.append((line_of(text, offset), f'forbidden import {spec}'))
    elif suffix == '.rs':
        for match in re.finditer(RS_FORBIDDEN, code):
            found.append((line_of(text, match.start()), f'forbidden dependency {match[0]}'))
    elif suffix == '.gd':
        for match in re.finditer(GD_FORBIDDEN, code):
            found.append((line_of(text, match.start()), f'forbidden engine API {match[0].strip()}'))
    return found

def ui_violations(suffix, text):
    """List (line, message) for hardcoded screen positions in a UI source file."""
    if suffix not in LANGS:
        return []
    no_comments, _ = strip_source(text, **LANGS[suffix])
    return [(line_of(text, m.start()), f'hardcoded position {m[0].strip()!r}; use layout containers')
            for m in re.finditer(UI_FORBIDDEN, no_comments)]

def scan(root=ROOT):
    errors = []
    for folder, check in ((CORE_DIR, core_violations), (UI_DIR, ui_violations)):
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(p for p in base.rglob('*') if p.is_file()):
            text = path.read_text(encoding='utf-8', errors='replace')
            for line, message in check(path.suffix.lower(), text):
                errors.append(f'{path.relative_to(root).as_posix()}:{line}: {message}')
    return errors

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    errors = scan()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        print(f'architecture FAILED ({len(errors)} violations); see ARCHITECTURE.md', file=sys.stderr)
        return 1
    print('architecture OK')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
