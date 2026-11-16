"""Version gates for the toolkit and its generated verification entrypoint."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (ROOT / 'bootstrap_harness.py', ROOT / 'template/tools/verify.py')
PROBE = '''
import pathlib
import runpy
import subprocess
import sys
from unittest.mock import patch

path, version, run_name = sys.argv[1:]
sys.argv = [path]
simulated = tuple(map(int, version.split('.'))) + ('final', 0)
with patch.object(sys, 'version_info', simulated), \\
     patch.object(pathlib.Path, 'mkdir', side_effect=AssertionError('filesystem work started')), \\
     patch.object(subprocess, 'run', side_effect=AssertionError('subprocess work started')):
    runpy.run_path(path, run_name=run_name)
'''


class PythonVersionTest(unittest.TestCase):
    def probe(self, path, version, run_name):
        with tempfile.TemporaryDirectory(prefix='harness-version-test-') as tmp:
            root = Path(tmp).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            result = subprocess.run(
                [sys.executable, '-c', PROBE, str(path), version, run_name], cwd=root,
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15,
            )
            self.assertEqual(list(root.iterdir()), [], 'Version checks must not create project files.')
            return result

    def test_unsupported_versions_fail_before_project_work(self):
        for path in ENTRYPOINTS:
            for version in ('3.9.0', '3.10.0'):
                with self.subTest(entrypoint=path.name, version=version):
                    result = self.probe(path, version, '__main__')
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn('Python 3.11+', result.stderr)
                    self.assertIn(version, result.stderr)
                    self.assertIn('Rerun', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertEqual(result.stdout, '')

    def test_supported_versions_can_load_entrypoints(self):
        for path in ENTRYPOINTS:
            for version in ('3.11.0', '.'.join(map(str, sys.version_info[:3]))):
                with self.subTest(entrypoint=path.name, version=version):
                    result = self.probe(path, version, 'version_probe')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, '')
                    self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
