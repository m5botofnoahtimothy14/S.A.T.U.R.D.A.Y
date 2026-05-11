                             
import logging

logger = logging.getLogger("SATURDAY.AI.IssueHandler")

class IssueHandler:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.event_bus.subscribe("security_alert", self.triage_issue)

    def triage_issue(self, data):
        logger.warning(f"Triaging system issue: {data}")
                                                     
        pass
