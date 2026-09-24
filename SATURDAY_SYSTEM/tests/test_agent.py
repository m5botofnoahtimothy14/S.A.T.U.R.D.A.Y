"""Tests for SATURDAY Agent + self-reading — backends mocked, no screen touched."""
import sys
from pathlib import Path
from unittest import TestCase, main as test_main
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from saturday import screen_operator as so
from saturday.agent import AgentRunner, AgentTask, TemplateBrain, research_plan, supervised_plan


def ok(**kw):
    d = {"success": True}
    d.update(kw)
    return d


class TestAgent(TestCase):
    def _runner(self, operator=None, answers=None, stored=None):
        operator = operator or MagicMock()
        stored = stored if stored is not None else []
        prompter = MagicMock(side_effect=answers or []) if answers is not None else None
        runner = AgentRunner(
            operator=operator,
            brain=TemplateBrain(),
            store_fn=lambda content, tags: (stored.append((content, tags)), f"id-{len(stored)}")[1],
            prompter=prompter,
            confirm=True,
        )
        return runner, operator, stored

    def test_research_plan_runs_alone_and_vaults(self):
        op = MagicMock()
        op.open_url.return_value = ok(url="https://x")
        op.screenshot.return_value = ok(path="p", width=10, height=10)
        op.read_screen.return_value = ok(path="p", text="finding one finding two", words=[])
        runner, _, stored = self._runner(operator=op)
        task = runner.run(AgentTask("research test", research_plan("test")))
        self.assertEqual(task.status, "done")
        self.assertEqual(len(stored), 1)
        self.assertIn("finding one", stored[0][0])
        self.assertIn("research", stored[0][1])
        op.open_url.assert_called_once()
        print("DONE: autonomous research test passed.")

    def test_supervised_do_asks_then_executes(self):
        op = MagicMock()
        op.open_app.return_value = ok(app="notepad")
        op.screenshot.return_value = ok(path="p", width=1, height=1)
        runner, _, _ = self._runner(operator=op, answers=["open notepad", "see", "done"])
        task = runner.run(AgentTask("open notepad for me", supervised_plan("open notepad for me")))
        self.assertEqual(task.status, "done")
        op.open_app.assert_called_once()
        op.screenshot.assert_called_once()
        print("DONE: supervised do test passed.")

    def test_remote_without_prompter_fails_gracefully(self):
        op = MagicMock()
        runner, _, _ = self._runner(operator=op, answers=None)
        runner.prompter = None
        task = runner.run(AgentTask("mystery goal", supervised_plan("mystery goal")))
        self.assertEqual(task.status, "failed")
        op.open_app.assert_not_called()
        print("DONE: remote no-prompt test passed.")

    def test_step_budget_stops_runaway(self):
        op = MagicMock()
        op.screenshot.return_value = ok(path="p")
        runner, _, _ = self._runner(operator=op, answers=["see"] * 50)
        runner.max_steps = 4
        task = runner.run(AgentTask("loop", supervised_plan("loop")))
        self.assertEqual(task.status, "stopped")
        print("DONE: step budget test passed.")

    def test_clicktext_uses_word_boxes(self):
        from saturday.screen_operator import ScreenOperator
        op = ScreenOperator()
        words = [{"text": "Compose", "x": 100, "y": 200, "w": 60, "h": 20, "conf": 95.0}]
        with patch.object(ScreenOperator, "read_screen",
                          return_value=ok(text="Compose", words=words)), \
             patch.object(ScreenOperator, "click", return_value=ok(x=130, y=210)) as mock_click:
            res = op.click_text("compose", confirm=True)
            self.assertTrue(res["success"])
            mock_click.assert_called_once_with(130, 210, confirm=True)
        print("DONE: click-by-text test passed.")

    def test_clicktext_gated_and_missing_word(self):
        from saturday.screen_operator import ScreenOperator
        op = ScreenOperator()
        denied = op.click_text("Compose", confirm=False)
        self.assertFalse(denied["success"])
        with patch.object(ScreenOperator, "read_screen",
                          return_value=ok(text="Inbox Settings", words=[
                              {"text": "Inbox", "x": 0, "y": 0, "w": 10, "h": 10, "conf": 90.0}])):
            missing = op.click_text("Compose", confirm=True)
            self.assertFalse(missing["success"])
            self.assertIn("not found", missing["error"])
        print("DONE: clicktext refusal test passed.")

    def test_read_reports_gracefully_without_ocr(self):
        from saturday.screen_operator import ScreenOperator
        op = ScreenOperator()
        with patch.object(so, "_OCR_AVAILABLE", False), \
             patch.object(so, "_OCR_ERROR", "no ocr here"):
            res = op.read_screen()
            self.assertFalse(res["success"])
            self.assertIn("no ocr here", res["error"])
        print("DONE: OCR fallback test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
