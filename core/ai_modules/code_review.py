                           
import structlog
import ast
from core.event_bus import EventBus

logger = structlog.get_logger("SATURDAY.AI.CodeReview")

class CodeReviewer:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe("code_review_request", self.perform_review)

    async def perform_review(self, code_str: str):
        logger.info("Starting code review...")
        try:
            tree = ast.parse(code_str)
            issues = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    issues.append(f"Import detected: {node.names[0].name}")
                if isinstance(node, ast.FunctionDef):
                    if len(node.args.args) > 5:
                        issues.append(f"Function {node.name} has too many arguments.")
            
            result = {"status": "success", "issues": issues}
            self.event_bus.publish("code_review_complete", result)
            return result
        except Exception as e:
            logger.error("Code review failed", error=str(e))
            return {"status": "error", "message": str(e)}
