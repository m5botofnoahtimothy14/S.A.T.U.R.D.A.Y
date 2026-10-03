import sys
sys.path.insert(0, r'D:\S.A.T.U.R.D.A.Y\core')

import importlib.util

# Test governance modules directly
# ConsentManager
spec = importlib.util.spec_from_file_location('consent_manager', r'D:\S.A.T.U.R.D.A.Y\core\governance\consent_manager.py')
cm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cm)
print('ConsentManager: OK')

# PrivacyMode
spec = importlib.util.spec_from_file_location('privacy_mode', r'D:\S.A.T.U.R.D.A.Y\core\governance\privacy_mode.py')
pm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pm)
print('PrivacyMode: OK')

# ComplianceLogger
spec = importlib.util.spec_from_file_location('compliance_logger', r'D:\S.A.T.U.R.D.A.Y\core\governance\compliance_logger.py')
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)
print('ComplianceLogger: OK')

# BiometricPolicy
spec = importlib.util.spec_from_file_location('biometric_policy', r'D:\S.A.T.U.R.D.A.Y\core\governance\biometric_policy.py')
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)
print('BiometricPolicy: OK')

# NotificationRouter
spec = importlib.util.spec_from_file_location('notification_router', r'D:\S.A.T.U.R.D.A.Y\core\communication\notification_router.py')
nr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nr)
print('NotificationRouter: OK')

# CodeWriter
spec = importlib.util.spec_from_file_location('code_writer', r'D:\S.A.T.U.R.D.A.Y\core\ai_modules\code_writer.py')
cw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cw)
print('CodeWriter: OK')

# SelfHealManager
from self_heal import SelfHealManager, HealingNeuralNetwork
print('SelfHealManager: OK')

# SelfRewriteAdvisor
spec = importlib.util.spec_from_file_location('self_rewrite', r'D:\S.A.T.U.R.D.A.Y\core\self_rewrite.py')
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)
print('SelfRewriteAdvisor: OK')

print('All stubs realigned successfully!')