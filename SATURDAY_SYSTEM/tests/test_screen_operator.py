"""Tests for SATURDAY Screen Operator — fully mocked, no real screen touched."""
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main as test_main
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from saturday import screen_operator as so
from saturday.screen_operator import ScreenOperator


def make_fake_pyautogui():
    fake = MagicMock()
    fake.size.return_value = (1920, 1080)
    fake.KEYBOARD_KEYS = ["enter", "esc", "tab", "a", "ctrl", "t", "win", "delete"]
    return fake


def with_backend(test_fn):
    """Run test_fn(operator, fake) with the pyautogui backend mocked."""
    fake = make_fake_pyautogui()
    with patch.object(so, "pyautogui", fake), patch.object(so, "_PYAUTOGUI_AVAILABLE", True):
        return test_fn(ScreenOperator(), fake)


class TestScreenOperator(TestCase):
    def test_click_requires_confirmation(self):
        def run(op, fake):
            denied = op.click(100, 200, confirm=False)
            self.assertFalse(denied["success"])
            self.assertIn("confirmation", denied["error"])
            fake.click.assert_not_called()
            ok = op.click(100, 200, confirm=True)
            self.assertTrue(ok["success"])
            fake.click.assert_called_once_with(100, 200)
        with_backend(run)
        print("DONE: click gating test passed.")

    def test_click_rejects_out_of_bounds(self):
        def run(op, fake):
            bad = op.click(5000, 50, confirm=True)
            self.assertFalse(bad["success"])
            self.assertIn("outside screen", bad["error"])
            fake.click.assert_not_called()
        with_backend(run)
        print("DONE: click bounds test passed.")

    def test_type_never_stores_content(self):
        def run(op, fake):
            secret = "my-super-secret-password-123"
            ok = op.type_text(secret, confirm=True)
            self.assertTrue(ok["success"])
            fake.write.assert_called_once()
            blob = str(op.history)
            self.assertNotIn(secret, blob)
            self.assertIn(str(len(secret)), blob)  # length only
        with_backend(run)
        print("DONE: type redaction test passed.")

    def test_press_rejects_unknown_key(self):
        def run(op, fake):
            bad = op.press("frobnicate", confirm=True)
            self.assertFalse(bad["success"])
            fake.press.assert_not_called()
            ok = op.press("enter", confirm=True)
            self.assertTrue(ok["success"])
        with_backend(run)
        print("DONE: press validation test passed.")

    def test_open_url_shortcuts_and_normalization(self):
        op = ScreenOperator()
        with patch("saturday.screen_operator.webbrowser") as wb:
            ok = op.open_url("gmail", confirm=True)
            self.assertTrue(ok["success"])
            self.assertEqual(ok["url"], "https://mail.google.com")
            ok = op.open_url("mail.google.com", confirm=True)
            self.assertEqual(ok["url"], "https://mail.google.com")
            bad = op.open_url("not a url at all", confirm=True)
            self.assertFalse(bad["success"])
            denied = op.open_url("https://example.com", confirm=False)
            self.assertFalse(denied["success"])
        print("DONE: open_url test passed.")

    def test_pixel_change_detects_difference(self):
        from PIL import Image
        tmp = Path(tempfile.mkdtemp(prefix="saturday_see_test_"))
        try:
            a = tmp / "a.png"
            b = tmp / "b.png"
            Image.new("RGB", (32, 32), (10, 10, 10)).save(a)
            Image.new("RGB", (32, 32), (10, 10, 10)).save(b)
            op = ScreenOperator()
            same = op.pixel_change(str(a), str(b))
            self.assertTrue(same["success"])
            self.assertAlmostEqual(same["changed_ratio"], 0.0)
            Image.new("RGB", (32, 32), (250, 250, 250)).save(b)
            diff = op.pixel_change(str(a), str(b))
            self.assertGreater(diff["changed_ratio"], 0.5)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        print("DONE: pixel verify test passed.")

    def test_core_gates_remote_screen_commands(self):
        from unittest.mock import MagicMock as MM
        from saturday.saturday_core import SATURDAYCore
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.pmv = MM()
        core.pmv.auto_lock_check.return_value = False
        core.is_running = True
        core._current_trusted = True
        core.screen = ScreenOperator()
        core._command_handlers = SATURDAYCore._build_command_handlers(core)
        fake = make_fake_pyautogui()
        with patch.object(so, "pyautogui", fake), patch.object(so, "_PYAUTOGUI_AVAILABLE", True):
            refused = core.process_command("click 100 200", trusted=False)
            self.assertIn("Remote callers cannot drive the screen", refused)
            fake.click.assert_not_called()
            # 'see' is read-only sensing: allowed for status visibility.
            with patch.object(ScreenOperator, "screenshot", return_value={"success": True, "path": "p", "width": 1, "height": 1}):
                seen = core.process_command("see", trusted=False)
            self.assertIn("Screen captured", seen)
        print("DONE: remote gating test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
