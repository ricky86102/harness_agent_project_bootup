"""Workflow guard regression tests: main-branch rules, agent command guard, phase parsing, runs branch."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import agent_guard
import git_guard as guard
import phase
import runs

class MessageTest(unittest.TestCase):
    def test_phase_subject_passes(self):
        self.assertEqual(guard.message_errors('phase(3): add subtitle pipeline\n'), [])

    def test_other_subjects_fail(self):
        for text in ('run: produce episode\n', 'feat: add thing\n', 'phase(x): bad number\n'):
            self.assertTrue(guard.message_errors(text), text)

    def test_long_subject_fails(self):
        self.assertTrue(guard.message_errors('phase(1): ' + 'x' * 80))

    def test_body_must_stay_short(self):
        ok = 'phase(2): ship editor\n\nWhy one.\nWhy two.\n\nCo-Authored-By: A <a@b.c>\n'
        self.assertEqual(guard.message_errors(ok), [])
        squash_log = 'phase(2): ship editor\n\n' + ''.join(f'    wip {i}\n' for i in range(9))
        self.assertTrue(any('concise' in e for e in guard.message_errors(squash_log)))

    def test_body_needs_blank_line_and_comments_ignored(self):
        self.assertTrue(guard.message_errors('phase(1): x\nbody\n'))
        self.assertEqual(guard.message_errors('# help\nphase(1): x\n# more\n'), [])

class PathTest(unittest.TestCase):
    def test_runs_paths(self):
        paths = ['runs', 'runs/ep12/run.json', 'src/core/a.py', 'runsheet.md', '']
        self.assertEqual(guard.runs_paths(paths), ['runs', 'runs/ep12/run.json'])

class AgentGuardTest(unittest.TestCase):
    PROTECTED = ('main',)

    def reason(self, command, branch='main'):
        return agent_guard.blocked_reason(command, branch, self.PROTECTED, 'runs')

    def test_hook_bypass_blocked(self):
        for command in ('git commit --no-verify -m x', 'git commit -nm x', 'git -c core.hooksPath=/dev/null commit -m x',
                        'git config core.hooksPath .githooks', 'git update-ref refs/heads/main abc',
                        'git push --force origin main', 'git merge --allow-unrelated-histories runs'):
            self.assertTrue(self.reason(command), command)

    def test_merge_on_main(self):
        self.assertTrue(self.reason('git merge phase/2-editor'))
        self.assertTrue(self.reason('git merge --ff-only phase/2-editor'))
        self.assertIsNone(self.reason('git merge --squash phase/2-editor'))
        self.assertIsNone(self.reason('git merge --ff-only origin/main'))
        self.assertIsNone(self.reason('git merge main', branch='phase/2-editor'))

    def test_runs_worktree_stays_on_runs(self):
        self.assertTrue(self.reason('git switch main', branch='runs'))
        self.assertTrue(self.reason('git checkout main', branch='runs'))
        self.assertIsNone(self.reason('git checkout -- ep1/run.json', branch='runs'))
        self.assertIsNone(self.reason('git switch phase/2-x', branch='main'))

    def test_double_force_clean_blocked(self):
        self.assertTrue(self.reason('git clean -ffdx'))
        self.assertTrue(self.reason('git clean -f -f -d'))
        self.assertIsNone(self.reason('git clean -fdx'))

    def test_normal_commands_pass(self):
        for command in ('git commit -m "phase(1): x"', 'git merge-base --is-ancestor main phase/2-x',
                        'git push origin main', 'git status'):
            self.assertIsNone(self.reason(command), command)

class PhaseParsingTest(unittest.TestCase):
    def test_current_phase(self):
        self.assertEqual(phase.current_phase('# R\n\n## Current State\n\nCurrent Phase: 4\n'), 4)
        with self.assertRaises(phase.PhaseError):
            phase.current_phase('no marker')

    def test_names(self):
        self.assertTrue(phase.SLUG.match('subtitle-pipeline'))
        self.assertFalse(phase.SLUG.match('Bad Slug'))
        self.assertEqual(phase.BRANCH.match('phase/12-subtitle-pipeline')[1], '12')

class RunsUnitTest(unittest.TestCase):
    def test_stamp_keeps_pipeline_fields(self):
        meta = runs.stamp({'duration': 61, 'run': 'old'}, 'ep1', 'accepted', 'abc', False, 'T')
        self.assertEqual(meta, {'duration': 61, 'run': 'ep1', 'summary': 'accepted', 'pipeline': 'abc',
                                'pipeline_dirty': False, 'recorded_at': 'T'})

    def test_missing_refspecs(self):
        existing = ['refs/heads/main:refs/heads/main']
        self.assertEqual(runs.missing_refspecs(existing, ('main', 'runs')), ['refs/heads/runs:refs/heads/runs'])

    def test_run_id(self):
        self.assertTrue(runs.RUN_ID.match('0047_the-raven'))
        self.assertFalse(runs.RUN_ID.match('../escape'))

@unittest.skipUnless(shutil.which('git'), 'git not installed')
class RunsIntegrationTest(unittest.TestCase):
    """setup creates an orphan runs worktree; record commits there and leaves the main branch untouched."""

    def git(self, *args, cwd=None):
        return subprocess.run(['git', *args], cwd=cwd or self.main, capture_output=True, text=True,
                              check=True).stdout.strip()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.main = Path(self.tmp.name, 'repo')
        self.main.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'test')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'core.autocrlf', 'false')

    def tearDown(self):
        subprocess.run(['git', 'worktree', 'remove', '--force', 'runs'], cwd=self.main, capture_output=True)
        self.tmp.cleanup()

    def test_setup_and_record(self):
        runs.setup(self.main)
        runs.setup(self.main)  # idempotent
        self.assertEqual(self.git('config', 'harness.mainBranch'), 'main')
        worktree = self.main / 'runs'
        self.assertEqual(self.git('branch', '--show-current', cwd=worktree), 'runs')
        self.git('add', '.gitignore')
        self.git('commit', '-qm', 'phase(1): scaffold')
        (worktree / 'ep1').mkdir()
        (worktree / 'ep1' / 'run.json').write_text('{"duration": 61}\n', encoding='utf-8')
        (worktree / 'ep1' / 'video.mp4').write_bytes(b'media')
        runs.record('ep1', 'accept episode one', self.main)
        meta = json.loads(self.git('show', 'runs:ep1/run.json'))
        self.assertEqual(meta['pipeline'], self.git('rev-parse', 'main'))
        self.assertEqual(meta['duration'], 61)
        self.assertEqual(self.git('log', '-1', '--format=%s', 'runs', '--'), 'run(ep1): accept episode one')
        self.assertNotIn('ep1/video.mp4', self.git('ls-tree', '-r', '--name-only', 'runs'))
        self.assertEqual(self.git('log', '--format=%s', 'main', '--'), 'phase(1): scaffold')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertIsNone(guard.git('merge-base', 'main', 'runs', cwd=self.main, check=False))

if __name__ == '__main__':
    unittest.main()
