"""Architecture checker regression tests: real violations fail, prose and strings do not."""
import tempfile
import unittest
from pathlib import Path
import check_architecture as arch

def messages(found):
    return [message for _, message in found]

class CorePythonTest(unittest.TestCase):
    def test_forbidden_import_fails(self):
        self.assertIn('forbidden import requests', messages(arch.core_violations('.py', 'import requests\n')))
        self.assertIn('forbidden import http.client', messages(arch.core_violations('.py', 'from http.client import X\n')))

    def test_forbidden_call_fails(self):
        self.assertEqual(arch.core_violations('.py', 'data = open("x")\n'), [(1, 'forbidden call open()')])

    def test_comments_and_strings_pass(self):
        text = '# uses http. and window. in prose\nNOTE = "requests.get socket fetch("\n"""import os"""\n'
        self.assertEqual(arch.core_violations('.py', text), [])

    def test_similar_names_pass(self):
        self.assertEqual(arch.core_violations('.py', 'import osmosis\nfrom .os import x\nsocket_count = 1\n'), [])

    def test_syntax_error_fails_closed(self):
        self.assertTrue(arch.core_violations('.py', 'def broken(:\n'))

class CoreScriptTest(unittest.TestCase):
    def test_js_imports_fail(self):
        text = "import axios from 'axios';\nconst fs = require('node:fs');\nimport('child_process');\n"
        self.assertEqual(messages(arch.core_violations('.ts', text)),
                         ['forbidden import axios', 'forbidden import node:fs', 'forbidden import child_process'])

    def test_js_globals_fail(self):
        found = arch.core_violations('.js', 'const w = window.innerWidth;\nfetch(url);\n')
        self.assertEqual(found, [(1, 'forbidden global window'), (2, 'forbidden global fetch')])

    def test_js_comments_strings_properties_pass(self):
        text = ("// call fetch( and window. here\n/* import x from 'axios' */\n"
                "const s = 'window.fetch http.get';\nconst t = `document`;\nstate.window = 1;\n")
        self.assertEqual(arch.core_violations('.ts', text), [])

    def test_go_imports(self):
        bad = 'package core\nimport (\n  "strings"\n  "net/http"\n)\n'
        self.assertEqual(messages(arch.core_violations('.go', bad)), ['forbidden import net/http'])
        self.assertEqual(arch.core_violations('.go', 'package core\n// import "os"\nimport "strings"\n'), [])

    def test_rust_and_gdscript(self):
        self.assertTrue(arch.core_violations('.rs', 'use std::fs::read;\n'))
        self.assertEqual(arch.core_violations('.rs', '// std::fs is banned\nlet s = "std::net";\n'), [])
        self.assertTrue(arch.core_violations('.gd', 'var f = FileAccess.open(p, 1)\n'))
        self.assertEqual(arch.core_violations('.gd', '# FileAccess is banned\nvar s = "OS"\n'), [])

class UiTest(unittest.TestCase):
    def test_absolute_position_fails(self):
        self.assertTrue(arch.ui_violations('.tsx', "const s = { position: 'absolute' };\n"))
        self.assertTrue(arch.ui_violations('.css', '.a { position: absolute; }\n'))
        self.assertTrue(arch.ui_violations('.gd', 'offset_left = 10\n'))

    def test_comments_pass(self):
        self.assertEqual(arch.ui_violations('.css', '/* never position: absolute */\n.a { display: flex; }\n'), [])
        self.assertEqual(arch.ui_violations('.gd', '# offset_left = 10\n'), [])

class ScanTest(unittest.TestCase):
    def test_scan_reports_path_and_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src/core').mkdir(parents=True)
            (root / 'src/core/a.py').write_text('x = 1\nimport socket\n', encoding='utf-8')
            self.assertEqual(arch.scan(root), ['src/core/a.py:2: forbidden import socket'])

if __name__ == '__main__':
    unittest.main()
