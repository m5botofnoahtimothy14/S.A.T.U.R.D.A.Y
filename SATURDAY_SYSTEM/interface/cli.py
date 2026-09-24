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
    - delete [id]              : Delete a stored entry.
    - search tag:[tag]         : Search memory by tag.
    - search                   : List recent memory entries.
    - status                   : Show system, vault, and node status.
    - heartbeat                : Manually update deadman switch.
    - sync                     : Trigger peer-to-peer sync.
    Screen (offline, drives real apps — no APIs needed):
    - open [app|url]           : Open app or site (e.g. open gmail).
    - see                      : Screenshot the screen for review.
    - click [x] [y]            : Click coordinates (see first).
    - type [text]              : Type into the focused window.
    - press / hotkey / scroll  : Keys and scrolling.
    - read                     : Read text off the screen.
    - clicktext [word]         : Click on-screen text, no coordinates.
    Autonomy (SATURDAY acts by itself):
    - research [topic]         : Search, read, vault findings alone.
    - do [goal]                : Work a goal alone (asks when unsure).
    - brain [goal]             : Unsupervised, local LLM decides.
    - tasks                    : Recent autonomous tasks.
    Senses (real local camera):
    - sense / mood / hr / wellness : People, mood, heart rate, composite.
    - drink [ml] / water       : Hydration log and level.
    Voice (local whisper + speech):
    - hear [sec] / say [text] / listen : Transcribe, speak, Jarvis loop.
    Identity + mind:
    - enroll / who / enrollvoice / voiceid / claps / mind / learn.
    Self-running:
    - glow / heal / assign / inbox / briefing / announce.
    Online free + cloud DB:
    - share [on|off] / cloudsetup / cloudbackup / cloudrestore.
    HUD + HomeBot Core2:
    - dashboard [port] / bot [cmd] / botstatus : HUD, drive, link status.
    Session (always-on):
    - services / cam / queue [goal] : Services, snapshot, background tasks.
    - docker [args] / maps / route : Containers, OSM maps + routing.
    - exit / quit              : Securely shut down and lock vaults.
        """
        print(help_text)
