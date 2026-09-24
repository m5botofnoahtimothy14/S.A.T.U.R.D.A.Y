"""Production smoke check: crypto round-trip + core E2E + status payload. No secrets written to repo."""
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from pmv.file_crypto import FileCrypto
from saturday.controller import MemoryController
from saturday.saturday_core import SATURDAYCore
from saturday.screen_operator import ScreenOperator


def main():
    tmp = Path(tempfile.mkdtemp(prefix="saturday_prod_check_"))
    try:
        controller = MemoryController("ProductionCheck123!", tmp)
        controller.mount_vaults()
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.project_root = tmp
        core.pmv = controller
        core.screen = ScreenOperator()
        core._current_trusted = True
        core.is_running = True
        core._command_handlers = SATURDAYCore._build_command_handlers(core)

        out = core.process_command("store production smoke test tag:prodcheck")
        assert "Stored securely" in out, out
        entry_id = out.rsplit(":", 1)[-1].strip()
        out = core.process_command(f"retrieve {entry_id}")
        assert "production smoke test" in out, out
        out = core.process_command("status")
        assert "ONLINE" in out, out
        payload = core.get_status_payload()
        assert payload["online"] is True and payload["vault_mounted"] is True
        controller.dismount_vaults()
        print("PRODUCTION SMOKE CHECK: PASS")
        return 0
    except Exception as e:
        print(f"PRODUCTION SMOKE CHECK: FAIL: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
