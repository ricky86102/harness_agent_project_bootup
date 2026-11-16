"""Model routing regression tests: dispatch checks, step budgets, stuck signals, agent definitions."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import agent_budget as budget

ROOT = Path(__file__).resolve().parents[1]
CONFIG = budget.load_config()
BRIEF = 'Tier: implementer-sonnet - rule 4: spec complete, acceptance is pytest\nAdd tests for x.'

def fresh():
    return budget.load_state(Path('missing-state-file.json'))

class DispatchTest(unittest.TestCase):
    def errors(self, **tool_input):
        return budget.dispatch_errors(tool_input, CONFIG)

    def test_valid_dispatch(self):
        self.assertEqual(self.errors(subagent_type='implementer-sonnet', prompt=BRIEF), [])
        self.assertEqual(self.errors(subagent_type='implementer-opus', effort='high',
                                     prompt='Tier: implementer-opus — rule 3: schema change\n...'), [])

    def test_rejections(self):
        self.assertTrue(self.errors(subagent_type='fork', prompt=BRIEF))
        self.assertTrue(self.errors(subagent_type='statusline-setup', prompt=BRIEF))
        self.assertTrue(self.errors(subagent_type='implementer-sonnet', model='opus', prompt=BRIEF))
        self.assertTrue(self.errors(subagent_type='implementer-sonnet', prompt='Add tests for x.'))
        self.assertTrue(self.errors(subagent_type='implementer-opus', prompt=BRIEF))  # Tier names another agent

    def test_builtin_agents_need_a_listed_model(self):
        explore = 'Tier: Explore - rule 2: locate callers of parse()\nFind them.'
        self.assertEqual(self.errors(subagent_type='Explore', model='haiku', prompt=explore), [])
        self.assertTrue(self.errors(subagent_type='Explore', prompt=explore))  # would inherit the session model
        self.assertTrue(self.errors(subagent_type='Explore', model='opus', prompt=explore))
        general = 'Tier: general-purpose - rule 4: rename helper per spec\nDo it.'
        self.assertEqual(self.errors(subagent_type='general-purpose', model='sonnet', prompt=general), [])
        self.assertTrue(self.errors(subagent_type='general-purpose', model='fable', prompt=general))
        self.assertTrue(self.errors(subagent_type='Explore', model='haiku', prompt='Find callers.'))

class BudgetTest(unittest.TestCase):
    def call(self, state, tool='Bash', agent='implementer-sonnet', **tool_input):
        return budget.pre_step(state, agent, tool, tool_input or {'command': f'echo {state["calls"]}'}, CONFIG)

    def test_budget_exhaustion_is_sticky(self):
        state, limit = fresh(), budget.budget_of('implementer-sonnet', CONFIG)
        for _ in range(limit):
            self.assertIsNone(self.call(state))
        self.assertIn('budget exhausted', self.call(state))
        self.assertIn('budget exhausted', self.call(state, tool='Read', file_path='a.py'))

    def test_identical_call_repeated_stops(self):
        state = fresh()
        for _ in range(CONFIG['repeat_limit'] - 1):
            self.assertIsNone(self.call(state, command='pytest tests/x'))
        self.assertIn('looping', self.call(state, command='pytest tests/x'))

    def test_same_file_edits_stop(self):
        state = fresh()
        for i in range(CONFIG['same_file_edits'] - 1):
            self.assertIsNone(self.call(state, tool='Edit', file_path='a.py', old_string=str(i), new_string='x'))
        self.assertIn('going in circles', self.call(state, tool='Edit', file_path='a.py', old_string='z', new_string='x'))

    def test_subagents_do_not_delegate(self):
        self.assertIn('do not delegate', self.call(fresh(), tool='Agent', subagent_type='researcher-haiku'))

    def test_reads_do_not_count_as_edits(self):
        state = fresh()
        self.call(state, tool='Read', file_path='a.py')
        self.assertEqual(state['edits'], {})
        self.assertEqual(state['read_streak'], 1)

    def test_warnings_fire_once(self):
        state = fresh()
        state['calls'] = budget.budget_of('implementer-sonnet', CONFIG)
        state['read_streak'] = CONFIG['read_streak']
        self.assertEqual(len(budget.post_step(state, 'implementer-sonnet', CONFIG)), 2)
        self.assertEqual(budget.post_step(state, 'implementer-sonnet', CONFIG), [])
        haiku = fresh()
        haiku['read_streak'] = 99
        self.assertEqual(budget.post_step(haiku, 'researcher-haiku', CONFIG), [])

class HookProcessTest(unittest.TestCase):
    """Run the hook as Claude Code does: JSON payload on stdin, exit 2 to block."""

    def run_hook(self, mode, payload, state_dir):
        env = dict(os.environ, AGENT_BUDGET_STATE=state_dir)
        return subprocess.run([sys.executable, str(Path(budget.__file__)), mode], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)

    def test_main_session_dispatch_and_subagent_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = {'tool_name': 'Agent', 'tool_input': {'subagent_type': 'general-purpose', 'prompt': 'x'}}  # no model
            self.assertEqual(self.run_hook('pre', bad, tmp).returncode, 2)
            self.assertEqual(self.run_hook('pre', {'tool_name': 'Bash', 'tool_input': {}}, tmp).returncode, 0)
            sub = {'session_id': 's1', 'agent_id': 'a1', 'agent_type': 'researcher-haiku', 'tool_name': 'Grep'}
            limit = budget.budget_of('researcher-haiku', CONFIG)
            codes = [self.run_hook('pre', dict(sub, tool_input={'pattern': f'p{i}'}), tmp).returncode
                     for i in range(limit + 1)]
            self.assertEqual(codes, [0] * limit + [2])

class DefinitionTest(unittest.TestCase):
    def frontmatter(self, name):
        text = (ROOT / '.claude' / 'agents' / f'{name}.md').read_text(encoding='utf-8')
        block = text.split('---')[1]
        return dict(line.split(':', 1) for line in block.strip().splitlines()), text

    def project_tiers(self):
        return {name: limits for name, limits in CONFIG['agents'].items() if 'models' not in limits}

    def test_every_tier_has_a_matching_definition(self):
        for name, limits in self.project_tiers().items():
            meta, text = self.frontmatter(name)
            self.assertEqual(meta['name'].strip(), name)
            self.assertGreater(int(meta['maxTurns']), limits['tool_calls'], 'maxTurns is the backstop behind the budget')
            self.assertIn('Status:', text)

    def test_builtin_entries_have_no_project_definition(self):
        for name, limits in CONFIG['agents'].items():
            if 'models' in limits:
                self.assertFalse((ROOT / '.claude' / 'agents' / f'{name}.md').exists(), name)
                self.assertTrue(set(limits['models']) <= {'haiku', 'sonnet', 'opus'}, name)

    def test_read_only_tier_has_no_write_tools(self):
        for name, limits in self.project_tiers().items():
            if limits.get('read_only'):
                tools = {t.strip() for t in self.frontmatter(name)[0]['tools'].split(',')}
                self.assertFalse(tools & (budget.WRITE_TOOLS | {'Bash', 'PowerShell', 'Agent'}), name)

    def test_policy_holds_no_threshold_numbers(self):
        for path in ('docs/model-routing.md', 'docs/hosts/claude.md', 'docs/hosts/codex.md'):
            policy = (ROOT / path).read_text(encoding='utf-8')
            self.assertIsNone(re.search(r'\b\d+\s*(?:%|tool calls|times)', policy),
                              f'{path}: thresholds belong in agent-budgets.json')

if __name__ == '__main__':
    unittest.main()
