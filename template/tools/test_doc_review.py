"""Document reviewer regression tests: scope, prompt assembly, reply validation and caching (fake CLI)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import check_docs as docs
import doc_review as review

ROOT = Path(__file__).resolve().parents[1]

class ScopeTest(unittest.TestCase):
    def test_governed_documents_only(self):
        for path in ('AGENTS.md', 'ARCHITECTURE.md', 'docs/work-modes.md', 'docs/exec-plans/active/p.md'):
            self.assertTrue(review.in_scope(path), path)
        for path in ('CLAUDE.md', 'docs/archive/a.md', 'README.md', 'src/core/a.py', 'tools/doc_review_prompt.md'):
            self.assertFalse(review.in_scope(path), path)

class PromptTest(unittest.TestCase):
    def test_frame_holds_no_policy_rules(self):
        frame = review.FRAME.read_text(encoding='utf-8')
        policy = (ROOT / review.POLICY).read_text(encoding='utf-8')
        state = docs.current_state(review.POLICY, policy)
        rules = [line.lstrip('-0123456789. ').strip() for line in state.splitlines()]
        for rule in [r for r in rules if len(r) >= 30]:
            self.assertNotIn(rule, frame, 'copy rules into the rubric source, not the prompt frame')

    def test_prompt_carries_runtime_sources(self):
        frame = review.FRAME.read_text(encoding='utf-8')
        prompt = review.build_prompt(frame, 'RULE-TEXT', 'OWNER-TABLE', ['docs/a.md'], '+added line', nonce='n0')
        for part in ('RULE-TEXT', 'OWNER-TABLE', '<<<FILES n0\ndocs/a.md\nFILES n0>>>', '+added line'):
            self.assertIn(part, prompt)
        self.assertNotIn('@@SECTIONS@@', prompt)

class EngineTest(unittest.TestCase):
    def test_selection_order(self):
        none = lambda name: None
        self.assertEqual(review.select_engine({}, 'codex', none), 'codex')
        self.assertEqual(review.select_engine({'CLAUDECODE': '1'}, '', none), 'claude')
        self.assertEqual(review.select_engine({'CODEX_SANDBOX': 'x'}, '', none), 'codex')
        self.assertEqual(review.select_engine({}, '', lambda n: n == 'codex' and 'codex'), 'codex')
        with self.assertRaises(review.ReviewError):
            review.select_engine({}, '', none)

class ReplyTest(unittest.TestCase):
    ISSUE = {'file': 'docs/a.md', 'line': 3, 'problem': 'filler', 'fix': 'cut it'}

    def test_validate(self):
        files = ['docs/a.md']
        self.assertEqual(review.validate({'verdict': 'pass', 'issues': []}, files), [])
        self.assertEqual(review.validate({'verdict': 'fail', 'issues': [self.ISSUE]}, files), [])
        outside = dict(self.ISSUE, file='src/x.py')
        self.assertTrue(review.validate({'verdict': 'fail', 'issues': [outside]}, files))
        self.assertTrue(review.validate({'verdict': 'pass', 'issues': [self.ISSUE]}, files))
        self.assertTrue(review.validate({'verdict': 'maybe', 'issues': []}, files))

    def test_parse_claude_envelope(self):
        envelope = json.dumps({'is_error': False, 'result': 'Here: {"verdict": "pass", "issues": []}'})
        self.assertEqual(review.parse('claude', envelope, 'missing'), {'verdict': 'pass', 'issues': []})
        with self.assertRaises(review.ReviewError):
            review.parse('claude', json.dumps({'is_error': True, 'result': 'auth expired'}), 'missing')
        with self.assertRaises(review.ReviewError):
            review.parse('claude', 'no json here', 'missing')

@unittest.skipUnless(shutil.which('git'), 'git not installed')
class ReviewFlowTest(unittest.TestCase):
    """review() with a fake CLI: only staged documents reach it, from an empty directory, once per content."""

    POLICY = '# Documentation Policy\n\n## Current State\n\n- One fact per line.\n\n## Records\n'

    def git(self, *args):
        subprocess.run(['git', *args], cwd=self.repo, check=True, capture_output=True)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'core.autocrlf', 'false')
        (self.repo / 'docs').mkdir()
        (self.repo / 'src').mkdir()
        (self.repo / review.POLICY).write_text(self.POLICY, encoding='utf-8')
        (self.repo / 'AGENTS.md').write_text('| Before you | Read |\n', encoding='utf-8')
        (self.repo / 'docs/a.md').write_text('# A\n\n- Run tests.\n', encoding='utf-8')
        (self.repo / 'src/secret.py').write_text('TOKEN = "code-only"\n', encoding='utf-8')
        self.git('add', '-A')
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def fake(self, verdict='pass', issues=(), returncode=0):
        def run(cmd, cwd, env, input, capture_output, timeout):
            self.calls.append({'cmd': cmd, 'cwd': Path(cwd), 'prompt': input.decode('utf-8'), 'env': env,
                               'listing': list(Path(cwd).iterdir())})
            reply = {'verdict': verdict, 'issues': list(issues)}
            Path(cmd[cmd.index('-o') + 1]).write_text(json.dumps(reply), encoding='utf-8')
            return subprocess.CompletedProcess(cmd, returncode, b'', b'boom')
        return run

    def run_review(self, runner):
        return review.review(cwd=self.repo, runner=runner, env={'CODEX_HOME': 'x', 'CLAUDECODE': '1'},
                             which=lambda name: name)

    def test_only_document_diff_reaches_reviewer_from_empty_dir(self):
        self.git('config', 'harness.reviewer', 'codex')
        self.assertEqual(self.run_review(self.fake()), 0)
        call = self.calls[0]
        self.assertIn('docs/a.md', call['prompt'])
        self.assertIn('- One fact per line.', call['prompt'])
        self.assertNotIn('code-only', call['prompt'])
        self.assertNotIn('secret.py', call['prompt'])
        self.assertEqual(call['listing'], [])
        self.assertNotIn('CLAUDECODE', call['env'])
        self.assertIn('read-only', call['cmd'])

    def test_approved_content_is_not_reviewed_twice(self):
        self.git('config', 'harness.reviewer', 'codex')
        self.assertEqual(self.run_review(self.fake()), 0)
        self.assertEqual(self.run_review(self.fake()), 0)
        self.assertEqual(len(self.calls), 1)

    def test_fail_verdict_blocks(self):
        self.git('config', 'harness.reviewer', 'codex')
        issue = {'file': 'docs/a.md', 'line': 3, 'problem': 'vague', 'fix': 'name the command'}
        self.assertEqual(self.run_review(self.fake('fail', [issue])), 1)

    def test_cli_failure_raises(self):
        self.git('config', 'harness.reviewer', 'codex')
        with self.assertRaises(review.ReviewError):
            self.run_review(self.fake(returncode=2))

    def test_oversized_diff_blocks_without_calling(self):
        (self.repo / 'docs/a.md').write_text('# A\n\n' + '- x\n' * (review.MAX_DIFF // 3), encoding='utf-8')
        self.git('add', '-A')
        self.assertEqual(self.run_review(self.fake()), 1)
        self.assertEqual(self.calls, [])

    def test_no_document_change_skips(self):
        self.git('reset', '-q', '--', 'docs', 'AGENTS.md')
        self.assertEqual(self.run_review(self.fake()), 0)
        self.assertEqual(self.calls, [])

if __name__ == '__main__':
    unittest.main()
