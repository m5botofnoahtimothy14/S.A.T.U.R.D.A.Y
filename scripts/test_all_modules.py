import py_compile
import sys

files = [
    r'D:\S.A.T.U.R.D.A.Y\core\self_rewrite.py',
    r'D:\S.A.T.U.R.D.A.Y\core\self_heal.py',
    r'D:\S.A.T.U.R.D.A.Y\core\system_monitor.py',
    r'D:\S.A.T.U.R.D.A.Y\core\admin_mood.py',
    r'D:\S.A.T.U.R.D.A.Y\core\ai_modules\code_writer.py',
    r'D:\S.A.T.U.R.D.A.Y\core\health\google_fit_integration.py',
    r'D:\S.A.T.U.R.D.A.Y\core\health\sensor_hub.py',
    r'D:\S.A.T.U.R.D.A.Y\core\ui\bridge.py',
    r'D:\S.A.T.U.R.D.A.Y\core\hybrid\edith\task_handler.py',
    r'D:\S.A.T.U.R.D.A.Y\core\distributed\interdevice_sync.py',
    r'D:\S.A.T.U.R.D.A.Y\core\homebot\mapping.py',
    r'D:\S.A.T.U.R.D.A.Y\core\governance\consent_manager.py',
    r'D:\S.A.T.U.R.D.A.Y\core\governance\privacy_mode.py',
    r'D:\S.A.T.U.R.D.A.Y\core\governance\compliance_logger.py',
    r'D:\S.A.T.U.R.D.A.Y\core\governance\biometric_policy.py',
    r'D:\S.A.T.U.R.D.A.Y\core\communication\notification_router.py',
]

passed = 0
failed = 0
for f in files:
    name = f.split('\\')[-1]
    try:
        py_compile.compile(f, doraise=True)
        print(f'OK  {name}')
        passed += 1
    except py_compile.PyCompileError as e:
        print(f'ERR {name}: {e}')
        failed += 1

print(f'\n{passed} passed, {failed} failed out of {len(files)}')
