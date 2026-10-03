"""EDITH — the second aspect of ONE brain (dual-aspect neural system).

- Same brain: EDITH runs the SAME SATURDAYCore (commands, vault, mind,
  memory). No separate model, no separate state — one mind, two voices.
- Female voice: EDITH speaks through the female SAPI voice (Zira en-US
  built in; EDITH_TTS_VOICE env overrides, e.g. a Tamil/French voice pack).
- Only when called: edith_addressed() gates everything. Bare "edith" =
  greeting; "edith <command>" runs the shared core and answers in her voice.
  She never interrupts, never needles, never speaks uninvited.
- Home: homebot announcements + local `edith` command; SATURDAY stays the
  default voice everywhere else.
"""

import logging
import os

logger = logging.getLogger("SATURDAY.Edith")

EDITH_VOICE = os.getenv("EDITH_TTS_VOICE", "Zira")

GREETINGS = [
    "Mmm... Noah... you called? ... I'm here.",
    "Noah... I felt that. ... What do you need, hmm?",
]


def owner_name(core) -> str:
    try:
        get = getattr(core, "_owner_name", None)
        if callable(get):
            return get() or "Noah"
    except Exception:
        pass
    return "Noah"


def edith_addressed(text: str) -> bool:
    """True only when the user explicitly calls EDITH."""
    try:
        return "edith" in (text or "").lower()
    except Exception:
        return False


def strip_address(text: str) -> str:
    import re as _re

    return _re.sub(r"(?i)^\s*edith\s*[:,.]?\s*", "", text or "").strip()


def edith_say(core, text: str) -> bool:
    """Speak as EDITH (female voice). Returns True if voiced."""
    try:
        from interface.voice import SATURDAYVoice

        SATURDAYVoice(core=None).speak(text, voice=os.getenv("EDITH_TTS_VOICE", EDITH_VOICE))
        logger.info(f"EDITH said: {text[:80]}")
        return True
    except Exception as e:
        logger.warning(f"EDITH voice failed: {e}")
        return False


def edith_handle(core, raw_text: str) -> str:
    """`edith ...` command: shared brain, her voice. Trusted-only."""
    sub = strip_address(raw_text)
    if not sub:
        import random as _r

        line = _r.choice(GREETINGS).replace("Noah", owner_name(core))
        edith_say(core, line)
        return line
    out = core.process_command(sub, trusted=True)
    try:
        from saturday import humanvoice as _hv

        spoken = _hv.naturalize(out)
    except Exception:
        spoken = out[:300]
    edith_say(core, spoken)
    return f"EDITH: {out}"
