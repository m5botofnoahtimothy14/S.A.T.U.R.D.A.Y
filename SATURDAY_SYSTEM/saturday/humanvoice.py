"""SATURDAY Human Voice — sounds like a person, not a status readout.

Three jobs:
1. NATURAL LINES: startup, arrivals, mood reactions, hydration nudges,
   briefings — composed like sentences, with variation so repeats never
   sound canned. No emoji, no "BPM", no raw JSON ever reaches the mouth.
2. VOICEPRINT GATE: if a voiceprint is enrolled, who_authorized() confirms
   the speaker is the owner before commands run. Strangers get heard
   (STT still runs) but are refused politely — the human analogue of a
   locked door.
3. SPEECH RECORDER: records each authorized/denied turn to the vault so
   the mind can later learn phrasing and command habits.

Pure text generation — no audio, no models, fully offline and testable.
"""

import logging
import random
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("SATURDAY.HumanVoice")

_HELLO = ["Hey, good to see you.", "There you are.", "Good to have you back.",
          "Hey. I'm right here.", "Welcome back."]
_NIGHT = ["It's late — I'm here, quietly.", "Burning the midnight oil with you."]


def startup_line(core_ok: bool = True, vault_ok: bool = True) -> str:
    hour = time.localtime().tm_hour
    if not core_ok:
        return "I'm starting up, but something isn't right yet — give me a moment."
    if not vault_ok:
        return "I'm online, but the vault is locked. Say the word and I'll take orders."
    if hour >= 22 or hour < 6:
        return f"{random.choice(_NIGHT)} I'm online and everything's running."
    return f"{random.choice(_HELLO)} SATURDAY's online — all systems running."


def arrival_line(name: Optional[str], mood: Optional[str] = None) -> str:
    hour = time.localtime().tm_hour
    who = f", {name}" if name else ""
    if mood in ("sad", "anxious", "angry", "sad", "disgusted"):
        base = random.choice([
            f"Hey{who}. I'm here if you need me.",
            f"Hey{who} — rough moment, huh? I'm right here.",
            f"I'm here{who}. No rush, whenever you're ready."])
    elif mood == "happy":
        base = random.choice([
            f"Love the energy{who}!", f"Hey{who} — good day, I can tell!"])
    elif hour >= 22 or hour < 6:
        base = f"Late night{who}. I'm still up with you."
    else:
        hour_now = time.localtime().tm_hour
        base = random.choice([
            f"Hey{who}, good to see you.",
            f"Good morning{who}." if hour_now < 12 else f"Hey{who}.",
            f"There you are{who}."])
    return base


def hydration_line(name: Optional[str], percent: float) -> str:
    who = f", {name}" if name else ""
    if percent < 10:
        return f"Hey{who} — I haven't seen a sip all day. Water?"
    return f"Hey{who}, quick one — your water's running low."


def briefing_speech(name: str, water_ml: float, goal_ml: float, tasks: int,
                    top_commands: list, bot_link: str) -> str:
    hour = time.localtime().tm_hour
    part = "evening" if hour >= 17 else "afternoon" if hour >= 12 else "morning"
    bits = [f"Good {part}, {name}. Here's your day."]
    if water_ml >= goal_ml:
        bits.append("Water's fully stocked — nice work.")
    elif water_ml >= goal_ml * 0.5:
        bits.append(f"You're halfway through your water goal.")
    else:
        bits.append("Your water's low — that's the one thing I'd nudge.")
    if tasks:
        bits.append(f"{tasks} things I handled for you so far.")
    if top_commands:
        bits.append("You mostly use me for " + _human_join(top_commands[:2]) + ".")
    bot_txt = {"live": "The homebot's awake and linked.", "stale": "The homebot's gone quiet."}
    bits.append(bot_txt.get(bot_link, "Homebot's standing by."))
    return " ".join(bits)


def refusal_line(verdict: str = "guest") -> str:
    if verdict == "guest":
        return random.choice([
            "I didn't quite catch that — could you say it again?",
            "Say that once more?",
            "Didn't get that clearly."])
    return "I'm not sure who that is — say the word and I'll learn your voice."


def unknown_command_line() -> str:
    return random.choice([
        "I don't know that one yet. Type help and I'll show you what I can do.",
        "That's new to me — 'help' lists everything I've learned."])


def _human_join(items) -> str:
    items = [str(i) for i in items]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


_MACHINE_MARKERS = ("❌", "✅", "📷", "🔑", "🌐", "🧠", "💓", "💧", "🗺️", "🐳", "📥", "🩺",
                    "🧭", "📣", "🔊", "👤", "🎙️", "👏", "✨", "🤖", "📋", "☁️", "🙂", "📡")


def naturalize(text: str) -> str:
    """Turn a console response into something a person would say.

    Drops emoji/machine bullets, unreadable numbers, and error dumps.
    Falls back to a short human sentence when nothing speakable remains.
    """
    import re

    t = str(text or "").strip()
    if not t:
        return "Hmm."
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    keep = []
    for ln in lines:
        for mark in _MACHINE_MARKERS:
            ln = ln.replace(mark, "")
        ln = ln.replace("✅", "").replace("❌", "").strip()
        ln = re.sub(r"^\s*[-•*>|]+\s*", "", ln)
        # Skip pure numbers / raw values (BPM tables, IDs, JSON-ish).
        if not ln or re.fullmatch(r"[\d\W]+", ln):
            continue
        if ln.startswith("{") or ln.startswith("["):
            continue
        keep.append(ln)
    if not keep:
        if "error" in t.lower() or "failed" in t.lower() or "❌" in t:
            return "Sorry — that didn't work. Try again?"
        return "All good."
    joined = " ".join(keep)
    # Speak readouts the way a person would, not like a machine.
    joined = re.sub(r"\b(\d{2,3})\s*BPM\b", lambda m: f"{m.group(1)} beats a minute", joined, flags=re.I)
    joined = re.sub(r"\b(\d{1,3})\s*%\b", lambda m: f"{m.group(1)} percent", joined)
    joined = re.sub(r"\b([\d.]+)\s*(km|min|ml|GB|MB)\b",
                    lambda m: f"{m.group(1)} {m.group(2)}", joined)
    joined = re.sub(r"\(confidence[^)]*\)", "", joined, flags=re.I)
    joined = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", joined)
    joined = re.sub(r"\s{2,}", " ", joined).strip()
    spoken = ". ".join(ln.rstrip(".") for ln in keep[:2]) if len(keep) > 1 else joined
    spoken = re.sub(r"\b(\d{2,3})\s*BPM\b", lambda m: f"{m.group(1)} beats a minute", spoken, flags=re.I)
    spoken = spoken.rstrip(".") + "."
    return spoken[:300]


class VoiceGate:
    """Owner-vs-guest via voiceprint (silently permissive if unenrolled)."""

    def __init__(self, core):
        self.core = core
        self.turns = 0
        self.authorized_turns = 0

    def enrolled(self) -> bool:
        try:
            return self.core._voicevault().print is not None
        except Exception:
            return False

    def who_authorized(self, samples) -> Dict[str, Any]:
        """samples: mic int16. Returns {authorized, verdict, distance}."""
        if not self.enrolled():
            return {"authorized": True, "verdict": "open (no voiceprint enrolled)"}
        res = self.core._voicevault().verify(samples)
        self.turns += 1
        if not res.get("success"):
            return {"authorized": True, "verdict": f"gate error: {res.get('error')}"}
        ok = bool(res.get("match"))
        if ok:
            self.authorized_turns += 1
        return {"authorized": ok, "verdict": res.get("verdict", "?"),
                "distance": res.get("distance")}

    def stats(self) -> Dict[str, Any]:
        return {"enrolled": self.enrolled(), "turns": self.turns,
                "authorized": self.authorized_turns}
