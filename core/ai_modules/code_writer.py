                           
import logging

logger = logging.getLogger("SATURDAY.AI.CodeWriter")

class CodeWriter:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.event_bus.subscribe("code_request", self.generate_code)

    def generate_code(self, data):
        prompt = data.get("prompt", "")
        language = data.get("language", "python")
        logger.info(f"Generating {language} code for: {prompt}")
        
        generated_code = f"# Generated {language} code\n# Prompt: {prompt}\n\ndef main():\n    print('Hello SATURDAY')\n"
        
        self.event_bus.publish("code_response", {"code": generated_code})
        return generated_code
