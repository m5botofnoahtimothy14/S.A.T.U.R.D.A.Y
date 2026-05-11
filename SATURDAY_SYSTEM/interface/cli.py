import os
import sys

class SATURDAYCLI:
    def __init__(self, core):
        self.core = core

    def run(self):
        """Main CLI loop."""
        print("\n🚀 SATURDAY CLI INTERFACE ACTIVE")
        print("Type 'help' for commands or 'exit' to quit.\n")

        while True:
            try:
                # Prompt
                user_input = input("SATURDAY ❯ ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("👋 Securing SATURDAY and exiting...")
                    break
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue

                # Pass to core
                response = self.core.process_command(user_input)
                print(f"\n{response}\n")

            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit securely.")
            except Exception as e:
                print(f"\n❌ CLI Error: {e}")

    def _show_help(self):
        help_text = """
    Available Commands:
    -------------------
    - store [content] tag:[tags] : Store data securely in PMV.
    - retrieve [id]            : Retrieve specific entry by ID.
    - search tag:[tag]         : Search memory by tag.
    - search                   : List recent memory entries.
    - status                   : Show system, vault, and node status.
    - heartbeat                : Manually update deadman switch.
    - sync                     : Trigger peer-to-peer sync.
    - exit / quit              : Securely shut down and lock vaults.
        """
        print(help_text)
