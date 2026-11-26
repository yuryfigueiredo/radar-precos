import re
import unittest
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "monitor.yml"
).read_text(encoding="utf-8")


class WorkflowTests(unittest.TestCase):
    def test_cache_restore_supports_windows_runner(self):
        self.assertIn("enableCrossOsArchive: true", WORKFLOW)

    def test_cache_tools_are_prepared_before_cache_steps(self):
        prepare_step = re.search(
            r"- name: Preparar ferramentas de cache\n(.*?)(?=\n      - name:|\Z)",
            WORKFLOW,
            re.DOTALL,
        )
        self.assertIsNotNone(prepare_step)
        self.assertIn("shell: bash", prepare_step.group(1))
        self.assertIn(r"C:\Program Files\Git\usr\bin", prepare_step.group(1))
        self.assertIn('>> "$GITHUB_PATH"', prepare_step.group(1))
        self.assertIn("gzip.exe", prepare_step.group(1))
        self.assertIn("--version", prepare_step.group(1))
        self.assertLess(
            WORKFLOW.index("- name: Preparar ferramentas de cache"),
            WORKFLOW.index("uses: actions/cache@v4"),
        )
        self.assertLess(
            WORKFLOW.index("- name: Preparar ferramentas de cache"),
            WORKFLOW.index("uses: actions/cache/save@v4"),
        )

    def test_history_is_saved_after_successful_run(self):
        save_step = re.search(
            r"- name: Persistir Hist[^\n]*\n(.*?)(?=\n      - name:|\Z)",
            WORKFLOW,
            re.DOTALL,
        )
        self.assertIsNotNone(save_step)
        self.assertIn("if: success()", save_step.group(1))
        self.assertIn("uses: actions/cache/save@v4", save_step.group(1))
        self.assertIn("key: price-history-${{ github.run_id }}", save_step.group(1))
        self.assertLess(WORKFLOW.index("python main.py"), WORKFLOW.index("actions/cache/save@v4"))

    def test_tests_run_before_real_collection(self):
        self.assertIn("python -m unittest discover -s tests -v", WORKFLOW)
        self.assertLess(
            WORKFLOW.index("python -m unittest discover -s tests -v"),
            WORKFLOW.index("python main.py"),
        )

    def test_overlapping_runs_are_serialized(self):
        self.assertIn("concurrency:", WORKFLOW)
        self.assertIn("cancel-in-progress: false", WORKFLOW)
        self.assertIn("timeout-minutes: 20", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
