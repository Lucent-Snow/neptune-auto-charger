import unittest
from pathlib import Path


class WorkflowScheduleTest(unittest.TestCase):
    def test_workflow_contains_eight_independent_schedule_entries(self):
        workflow = Path(__file__).parent / ".github" / "workflows" / "auto-charge.yml"
        content = workflow.read_text(encoding="utf-8")

        expected_crons = {
            "47 18 * * *",
            "17 19 * * *",
            "47 19 * * *",
            "17 20 * * *",
            "47 20 * * *",
            "17 21 * * *",
            "47 21 * * *",
            "7 22 * * *",
        }

        self.assertEqual(content.count("    - cron:"), 8)
        for cron in expected_crons:
            self.assertIn(f"    - cron: '{cron}'", content)

        self.assertNotIn("concurrency:", content)


if __name__ == "__main__":
    unittest.main()
