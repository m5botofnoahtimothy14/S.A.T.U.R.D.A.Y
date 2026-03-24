# core/rbac.py
from core.state import SystemState
import logging

logger = logging.getLogger("AEGIS.RBAC")
logger.setLevel(logging.INFO)

class RBAC:
    def __init__(self, system_state: SystemState):
        self.state = system_state
        # Define real access rules
        self.roles = {
            "Sir": ["all_modules", "security_override", "homebot_control", "edith_control"],
            "Noah": ["basic_modules", "edith_control"],
            "guest": ["edith_basic", "read_only"]
        }
        self.user_mode = self.state.get_state("user_mode", "Sir")

    def can_execute(self, module_name):
        """
        Returns True if current user_role can access module_name
        """
        allowed = False
        for role, permissions in self.roles.items():
            if self.user_mode.lower() == role.lower():
                if "all_modules" in permissions or module_name in permissions:
                    allowed = True
        if not allowed:
            logger.warning(f"RBAC: User '{self.user_mode}' denied access to {module_name}")
        return allowed

    def set_user_mode(self, mode):
        self.user_mode = mode
        self.state.update_state("user_mode", mode)
        logger.info(f"RBAC: User mode changed to {mode}")
