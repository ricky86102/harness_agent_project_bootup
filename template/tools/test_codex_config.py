"""Cross-file consistency of Codex role definitions and the dispatch allowlist."""
import json
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILTIN_TIERS = {
    'explorer': ('researcher-terra',),
    'worker': ('implementer-sol', 'implementer-astra'),
    'default': ('implementer-sol', 'implementer-astra'),
}


class CodexDefinitionTest(unittest.TestCase):
    def setUp(self):
        config_dir = ROOT / '.codex'
        self.entries = json.loads((config_dir / 'agent-budgets.json').read_text(encoding='utf-8'))['agents']
        self.definitions = {
            path.stem: tomllib.loads(path.read_text(encoding='utf-8'))
            for path in (config_dir / 'agents').glob('*.toml')
        }

    def test_custom_definitions_and_budgets_match_in_both_directions(self):
        custom = {name for name, entry in self.entries.items() if 'models' not in entry}
        self.assertTrue(custom, 'The Codex role definitions must not disappear together.')
        self.assertEqual(set(self.definitions), custom)
        for name, definition in self.definitions.items():
            with self.subTest(agent=name):
                self.assertEqual(definition['name'], name)

    def test_custom_agents_pin_model_and_effort(self):
        for name, definition in self.definitions.items():
            with self.subTest(agent=name):
                for field in ('model', 'model_reasoning_effort', 'description', 'developer_instructions'):
                    self.assertIsInstance(definition.get(field), str, f'{name}: missing {field}')
                    self.assertTrue(definition[field].strip(), f'{name}: empty {field}')

    def test_builtins_do_not_shadow_custom_definitions(self):
        builtins = {name for name, entry in self.entries.items() if 'models' in entry}
        self.assertEqual(builtins, set(BUILTIN_TIERS))
        self.assertFalse(builtins & set(self.definitions))

    def test_builtin_models_match_their_mapped_custom_tiers(self):
        for name, tiers in BUILTIN_TIERS.items():
            with self.subTest(agent=name):
                entry = self.entries[name]
                self.assertIsInstance(entry['models'], list)
                self.assertEqual(set(entry['models']), {self.definitions[tier]['model'] for tier in tiers})
                self.assertEqual(len(entry['models']), len(set(entry['models'])), 'Duplicate allowed model')
                for tier in tiers:
                    self.assertEqual(bool(entry.get('read_only')), bool(self.entries[tier].get('read_only')))


if __name__ == '__main__':
    unittest.main()
