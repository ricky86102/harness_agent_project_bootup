"""Single entrypoint for full project verification."""
import sys

if sys.version_info < (3, 11):
    sys.exit(
        '[ERROR] Python 3.11+ is required; running {}.{}.{}. '
        'Rerun this command with Python 3.11 or newer.'.format(*sys.version_info[:3])
    )

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_command(cmd, name):
    print(f"--> [Running] {name}...")
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        print(f"[FAIL] {name} failed!", file=sys.stderr)
        sys.exit(res.returncode)

def main():
    # 1. Documentation budget and planning invariants (working tree)
    run_command([sys.executable, "tools/check_docs.py"], "Documentation check")
    # 2. Architectural boundary check
    run_command([sys.executable, "tools/check_architecture.py"], "Architecture boundary check")
    # 3. Harness regression tests (tools/test_*.py)
    run_command([sys.executable, "-m", "unittest", "discover", "-s", "tools", "-p", "test_*.py"],
                "Harness regression tests")
    # 4. Domain unit tests (hook up your pytest / npm test / cargo test here)
    # run_command(["pytest"], "Unit tests")
    print("\n[SUCCESS] All checks passed! Project is healthy.")

if __name__ == '__main__':
    main()
