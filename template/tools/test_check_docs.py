"""Documentation guard regression tests."""
import unittest
from pathlib import Path
import check_docs as docs

class DocsRegressionTest(unittest.TestCase):
    def test_link_destination(self):
        self.assertEqual(docs.link_destination("docs/sub/a.md", "../b.md"), "docs/b.md")
        self.assertIsNone(docs.link_destination("docs/a.md", "http://example.com"))

    def test_headings_parsing(self):
        sample = "# Title\n\n## Current State\n\nFact.\n\n## Records\n\n### 2026-09-28 Title\n\nLog.\n"
        state, entries, _ = docs.parse_document("test.md", sample)
        self.assertEqual(state, "Fact.")
        self.assertEqual(len(entries), 1)

class PlanningRulesTest(unittest.TestCase):
    ROADMAP = "# Roadmap\n\n## Current State\n\nCurrent Phase: 2\n\n- Phase 2: active, [plan](active/p2.md)\n\n## Records\n"
    PLAN = "# P2\n\n## Current State\n\nStatus: x\nNext Step: y\nBlockers: none\nRoadmap: Phase 2\n\n## Records\n"

    def texts(self, **extra):
        texts = {docs.ROADMAP: self.ROADMAP, docs.ACTIVE_DIR + "p2.md": self.PLAN}
        texts.update(extra)
        return texts

    def test_valid_plan_passes(self):
        self.assertEqual(docs.check_planning(self.texts()), [])

    def test_no_active_plan_is_allowed(self):
        self.assertEqual(docs.check_planning({docs.ROADMAP: "# R\n\n## Current State\n\n- Phase 1\n\n## Records\n"}), [])

    def test_missing_roadmap(self):
        errors = docs.check_planning({docs.ACTIVE_DIR + "p2.md": self.PLAN})
        self.assertIn("roadmap missing", errors[0])

    def test_two_active_plans(self):
        errors = docs.check_planning(self.texts(**{docs.ACTIVE_DIR + "p3.md": self.PLAN}))
        self.assertTrue(any("at most one active plan" in e for e in errors))

    def test_missing_roadmap_line(self):
        plan = self.PLAN.replace("Roadmap: Phase 2\n", "")
        errors = docs.check_planning(self.texts(**{docs.ACTIVE_DIR + "p2.md": plan}))
        self.assertTrue(any('Roadmap: Phase <N>' in e for e in errors))

    def test_phase_not_in_roadmap(self):
        plan = self.PLAN.replace("Phase 2", "Phase 7")
        errors = docs.check_planning(self.texts(**{docs.ACTIVE_DIR + "p2.md": plan}))
        self.assertTrue(any("Phase 7 is not listed" in e for e in errors))

    def test_roadmap_must_link_active_plan(self):
        roadmap = self.ROADMAP.replace("[plan](active/p2.md)", "plan")
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any("must link to the active plan" in e for e in errors))

    def test_nested_files_count_as_active_plans(self):
        self.assertEqual(docs.active_plans({docs.ACTIVE_DIR + "sub/x.md": "", docs.ACTIVE_DIR + "a.md": ""}),
                         [docs.ACTIVE_DIR + "a.md", docs.ACTIVE_DIR + "sub/x.md"])

    def test_nested_plans_cannot_bypass_limit(self):
        texts = {docs.ROADMAP: self.ROADMAP, docs.ACTIVE_DIR + "a/p.md": self.PLAN, docs.ACTIVE_DIR + "b/p.md": self.PLAN}
        errors = docs.check_planning(texts)
        self.assertTrue(any("at most one active plan" in e for e in errors))

    def test_phase_only_in_records_fails(self):
        roadmap = ("# Roadmap\n\n## Current State\n\n- Phase 1: done\n\n## Records\n\n"
                   "### 2026-09-28 Old\n\n- Phase 2: active, [plan](active/p2.md)\n")
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any("must link to the active plan" in e for e in errors))
        self.assertTrue(any("Phase 2 is not listed" in e for e in errors))

    def test_roadmap_line_only_in_plan_records_fails(self):
        plan = self.PLAN.replace("Roadmap: Phase 2\n", "") + "\n### 2026-09-28 Old\n\nRoadmap: Phase 2\n"
        errors = docs.check_planning(self.texts(**{docs.ACTIVE_DIR + "p2.md": plan}))
        self.assertTrue(any('Roadmap: Phase <N>' in e for e in errors))

    def test_phase_line_must_link_plan(self):
        roadmap = self.ROADMAP.replace("- Phase 2: active, [plan](active/p2.md)",
                                       "- Phase 1: done, [plan](active/p2.md)\n- Phase 2: active")
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any("Phase 2 line must link" in e for e in errors))

    def test_completed_phase_cannot_hold_active_plan(self):
        roadmap = self.ROADMAP.replace("Current Phase: 2", "Current Phase: 3").replace(
            "Phase 2: active", "Phase 2: complete")
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any("not the roadmap Current Phase 3" in e for e in errors))

    def test_missing_current_phase_marker(self):
        roadmap = self.ROADMAP.replace("Current Phase: 2\n\n", "")
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any('Current Phase: <N>' in e for e in errors))

    def test_malformed_roadmap_fails_closed(self):
        roadmap = self.ROADMAP + "loose text without a record heading\n"
        errors = docs.check_planning(self.texts(**{docs.ROADMAP: roadmap}))
        self.assertTrue(any("must link to the active plan" in e for e in errors))

class WritingRulesTest(unittest.TestCase):
    def test_terse_document_passes(self):
        self.assertEqual(docs.check_writing({"docs/a.md": "# A\n\n- Run `python x.py`.\n"}), [])

    def test_long_line_fails(self):
        errors = docs.check_writing({"docs/a.md": "# A\n\n" + "word " * 50 + "\n"})
        self.assertTrue(any("docs/a.md:3:" in e and "one fact per line" in e for e in errors))

    def test_code_block_is_exempt(self):
        text = "# A\n\n```text\n" + "x" * 300 + "\nPlease note this.\n```\n"
        self.assertEqual(docs.check_writing({"docs/a.md": text}), [])

    def test_filler_fails_unless_inline_code(self):
        errors = docs.check_writing({"AGENTS.md": "# A\n\nPlease note that tests run first.\n"})
        self.assertTrue(any('filler phrase' in e for e in errors))
        self.assertEqual(docs.check_writing({"AGENTS.md": "- Avoid `in order to`.\n"}), [])

    def test_repeated_rule_across_documents_fails(self):
        rule = "- Phase work happens only in a phase worktree and reaches the main branch through a squash merge.\n"
        errors = docs.check_writing({"AGENTS.md": rule, "docs/work-modes.md": rule})
        self.assertTrue(any("repeats" in e for e in errors))
        self.assertEqual(docs.check_writing({"docs/a.md": rule + rule}), [])

    def test_archive_is_exempt(self):
        self.assertEqual(docs.check_writing({"docs/archive/a.md": "Please note " + "x" * 300}), [])

    def test_policy_state_limit_is_higher(self):
        state = "- fact\n" * 340  # about 2,380 characters
        doc = "# P\n\n## Current State\n\n" + state + "\n## Records\n"
        snapshot = type("S", (), {"texts": {}, "exists": lambda self, name: True})()
        for name, ok in ((docs.POLICIES[0], True), ("docs/other.md", False)):
            snapshot.texts = {name: doc}
            errors = [e for e in docs.check_snapshot(snapshot) if e.startswith(name + ": current state")]
            self.assertEqual(not errors, ok, name)

class RoutingRulesTest(unittest.TestCase):
    AGENTS = "".join(f"[p]({p})\n" for p in docs.POLICIES)

    def texts(self, agents=None, skip=None):
        texts = {p: "" for p in docs.POLICIES if p != skip}
        texts["AGENTS.md"] = self.AGENTS if agents is None else agents
        return texts

    def test_all_policies_routed(self):
        self.assertEqual(docs.check_routes(self.texts()), [])

    def test_missing_route(self):
        agents = self.AGENTS.replace("[p](docs/autonomous-mode.md)\n", "")
        errors = docs.check_routes(self.texts(agents=agents))
        self.assertTrue(any("must route to docs/autonomous-mode.md" in e for e in errors))

    def test_missing_policy_file(self):
        errors = docs.check_routes(self.texts(skip="docs/documentation-policy.md"))
        self.assertTrue(any("docs/documentation-policy.md: required policy document missing" in e for e in errors))

if __name__ == '__main__':
    unittest.main()
