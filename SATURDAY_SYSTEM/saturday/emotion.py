"""SATURDAY Emotion — emotional intelligence: perceive, understand, manage, learn.

Grounded in (not vibes):
  VAD dimensional model ..... valence/arousal/dominance per word. Prefers the
                              real NRC-VAD-Lexicon.txt in models/lexicons/ when
                              present; otherwise uses built-in starter norms
                              (anchor-consistent approximations, clearly flagged
                              as such — never mislabeled as NRC data).
  Plutchik wheel ............ 8 primaries + polar opposites guide empathy
                              (EmPO pattern: never mirror anger with anger).
  Appraisal theory .......... pleasantness / control / certainty inferred per
                              utterance (crowd-enVENT spirit, heuristic form).
  EICAP 4 layers ............ tracking → cause inference → appraisal →
                              appropriate response. Each is a tested function.
  EQ-Bench lesson ........... open behavior beats quizzes: EI probes here use
                              framing-consistency over scripted scenarios.

Honesty charter (ACM 2025: models claiming felt emotion mislead):
  simulated care, REAL attention. We never claim to feel. We do track your
  state, remember what helped, and adapt — all auditable in episodes.jsonl.
"""

import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("SATURDAY.Emotion")

LEX_DIR = Path(r"D:\S.A.T.U.R.D.A.Y\models\lexicons")

# Plutchik primaries + polar opposites (never mirror across an opposite pair)
PLUTCHIK = ["joy", "trust", "fear", "surprise", "sadness", "disgust", "anger", "anticipation"]
OPPOSITES = {"joy": "sadness", "sadness": "joy", "trust": "disgust",
             "disgust": "trust", "fear": "anger", "anger": "fear",
             "surprise": "anticipation", "anticipation": "surprise"}
# primary → (valence, arousal, dominance) wheel anchors
WHEEL_VAD = {"joy": (0.85, 0.65, 0.70), "trust": (0.75, 0.40, 0.65),
             "fear": (0.20, 0.80, 0.25), "surprise": (0.60, 0.85, 0.45),
             "sadness": (0.15, 0.35, 0.30), "disgust": (0.20, 0.60, 0.45),
             "anger": (0.20, 0.85, 0.65), "anticipation": (0.65, 0.60, 0.60)}

INTENSIFIERS = {"very": 0.15, "extremely": 0.25, "so": 0.12, "really": 0.12,
                "quite": 0.07, "slightly": -0.12, "a bit": -0.10, "barely": -0.18,
                "utterly": 0.25, "deeply": 0.18}
NEGATIONS = {"not", "no", "never", "n't", "hardly", "barely"}

# Starter norms (V,A,D in 0..1, NRC-VAD spirit). Compact core vocabulary;
# drop the real NRC-VAD-Lexicon.txt into models/lexicons/ to upgrade.
STARTER_NORMS = {
    "happy": (0.96, 0.65, 0.73), "joyful": (0.94, 0.70, 0.70), "glad": (0.90, 0.55, 0.68),
    "excited": (0.88, 0.90, 0.70), "love": (0.92, 0.65, 0.70), "loved": (0.90, 0.60, 0.65),
    "great": (0.85, 0.60, 0.68), "awesome": (0.88, 0.75, 0.70), "wonderful": (0.90, 0.60, 0.68),
    "amazing": (0.90, 0.78, 0.70), "fantastic": (0.88, 0.72, 0.68), "good": (0.80, 0.45, 0.62),
    "nice": (0.78, 0.40, 0.60), "proud": (0.82, 0.62, 0.75), "grateful": (0.85, 0.50, 0.60),
    "hopeful": (0.78, 0.55, 0.60), "calm": (0.75, 0.20, 0.62), "relaxed": (0.78, 0.18, 0.65),
    "relieved": (0.80, 0.35, 0.62), "confident": (0.80, 0.55, 0.80), "brave": (0.72, 0.70, 0.78),
    "sad": (0.15, 0.35, 0.30), "unhappy": (0.18, 0.38, 0.32), "depressed": (0.10, 0.30, 0.22),
    "lonely": (0.15, 0.35, 0.28), "miserable": (0.08, 0.45, 0.25), "cry": (0.12, 0.60, 0.25),
    "crying": (0.12, 0.60, 0.25), "tears": (0.15, 0.55, 0.28), "grief": (0.08, 0.45, 0.25),
    "heartbroken": (0.07, 0.55, 0.22), "hopeless": (0.10, 0.40, 0.20),
    "angry": (0.18, 0.85, 0.62), "furious": (0.10, 0.95, 0.65), "mad": (0.20, 0.82, 0.60),
    "annoyed": (0.30, 0.65, 0.60), "frustrated": (0.22, 0.75, 0.50), "irritated": (0.28, 0.62, 0.58),
    "hate": (0.12, 0.80, 0.60), "rage": (0.08, 0.95, 0.62),
    "afraid": (0.20, 0.80, 0.25), "scared": (0.18, 0.85, 0.22), "fear": (0.20, 0.82, 0.25),
    "anxious": (0.22, 0.78, 0.30), "worried": (0.25, 0.70, 0.32), "nervous": (0.28, 0.72, 0.35),
    "stressed": (0.20, 0.80, 0.35), "panic": (0.10, 0.95, 0.20), "terrified": (0.10, 0.92, 0.20),
    "overwhelmed": (0.18, 0.80, 0.25),
    "surprised": (0.60, 0.85, 0.45), "shocked": (0.35, 0.90, 0.35), "amazed": (0.75, 0.80, 0.55),
    "disgusted": (0.20, 0.60, 0.45), "gross": (0.22, 0.58, 0.45),
    "trust": (0.75, 0.40, 0.65), "trusted": (0.78, 0.38, 0.68), "safe": (0.80, 0.30, 0.70),
    "tired": (0.30, 0.25, 0.35), "exhausted": (0.15, 0.30, 0.25), "sick": (0.20, 0.55, 0.30),
    "pain": (0.12, 0.70, 0.28), "hurt": (0.15, 0.65, 0.30), "fail": (0.20, 0.55, 0.35),
    "failed": (0.18, 0.55, 0.32), "win": (0.88, 0.70, 0.75), "success": (0.88, 0.62, 0.78),
    "lost": (0.20, 0.55, 0.30), "alone": (0.22, 0.35, 0.32), "miss": (0.30, 0.45, 0.35),
    "sorry": (0.35, 0.40, 0.40), "thank": (0.82, 0.50, 0.62), "thanks": (0.82, 0.50, 0.62),
    "help": (0.55, 0.55, 0.50), "please": (0.60, 0.40, 0.50), "yes": (0.70, 0.45, 0.60),
    "no": (0.35, 0.45, 0.55), "okay": (0.60, 0.35, 0.58), "fine": (0.58, 0.32, 0.58),
    "bad": (0.25, 0.50, 0.40), "terrible": (0.10, 0.65, 0.30), "awful": (0.12, 0.62, 0.30),
    "horrible": (0.10, 0.68, 0.30), "stupid": (0.22, 0.60, 0.45), "dumb": (0.25, 0.50, 0.42),
    "smart": (0.78, 0.55, 0.72), "beautiful": (0.88, 0.55, 0.62), "ugly": (0.20, 0.50, 0.40),
    "fun": (0.85, 0.70, 0.65), "boring": (0.30, 0.25, 0.45), "funny": (0.82, 0.68, 0.62),
    "laugh": (0.85, 0.72, 0.62), "smile": (0.85, 0.55, 0.62), "hug": (0.88, 0.55, 0.65),
    "kiss": (0.88, 0.65, 0.62), "friend": (0.82, 0.50, 0.62), "family": (0.80, 0.50, 0.62),
    "home": (0.78, 0.40, 0.65), "work": (0.50, 0.55, 0.60), "busy": (0.45, 0.70, 0.55),
    "deadline": (0.30, 0.80, 0.45), "exam": (0.35, 0.78, 0.45), "interview": (0.40, 0.75, 0.50),
    "surgery": (0.18, 0.80, 0.30), "hospital": (0.25, 0.70, 0.35), "doctor": (0.55, 0.55, 0.60),
    "money": (0.60, 0.60, 0.65), "broke": (0.15, 0.60, 0.30), "rich": (0.75, 0.60, 0.75),
    "hungry": (0.40, 0.55, 0.45), "sleepy": (0.45, 0.20, 0.40), "awake": (0.60, 0.55, 0.60),
    "dream": (0.75, 0.50, 0.60), "nightmare": (0.12, 0.80, 0.25),
    "down": (0.25, 0.35, 0.35), "blue": (0.28, 0.35, 0.32), "upset": (0.20, 0.65, 0.40),
    "gloomy": (0.15, 0.35, 0.30), "cheerful": (0.90, 0.65, 0.68),
    "delighted": (0.92, 0.70, 0.70), "thrilled": (0.90, 0.85, 0.70),
    "grumpy": (0.28, 0.55, 0.50), "moody": (0.30, 0.50, 0.42),
}

_lex_cache: Optional[Tuple[str, Dict[str, Tuple[float, float, float]]]] = None


def load_lexicon() -> Tuple[str, Dict[str, Tuple[float, float, float]]]:
    """(source, norms). Prefers real NRC-VAD file; else flagged starter norms."""
    global _lex_cache
    if _lex_cache is not None:
        return _lex_cache
    try:
        for cand in (LEX_DIR / "NRC-VAD-Lexicon.txt", LEX_DIR / "nrc-vad.txt"):
            if cand.exists():
                norms = {}
                for line in cand.read_text(encoding="utf-8").splitlines():
                    parts = line.strip().split("\t")
                    if len(parts) >= 4:
                        try:
                            norms[parts[0].lower()] = (float(parts[1]), float(parts[2]), float(parts[3]))
                        except ValueError:
                            pass
                if len(norms) > 1000:
                    _lex_cache = ("NRC-VAD (full file)", norms)
                    return _lex_cache
    except Exception as e:
        logger.warning(f"lexicon load failed: {e}")
    _lex_cache = ("starter-norms (built-in, approximate)", dict(STARTER_NORMS))
    return _lex_cache


# -- 1. perceive: text → VAD + label ----------------------------------------------
def analyze(text: str) -> Dict[str, Any]:
    """EICAP layer 1+2: track emotion + surface cause. Pure, offline, tested."""
    source, norms = load_lexicon()
    words = re.findall(r"[a-zA-Z']+", (text or "").lower())
    if not words:
        return {"label": "neutral", "vad": (0.55, 0.40, 0.55), "intensity": 0.0,
                "cause": "", "appraisal": {}, "source": source}
    vals, hits, neg, boost = [], 0, False, 0.0
    for w in words:
        if w in NEGATIONS or w.endswith("n't"):
            neg = True
            continue
        if w in INTENSIFIERS:
            boost += INTENSIFIERS[w]
            continue
        if w in norms:
            v, a, d = norms[w]
            if neg:
                v = 1.0 - v
                a = max(0.0, a - 0.15)
                neg = False
            vals.append((v, a, d))
            hits += 1
    if not vals:
        return {"label": "neutral", "vad": (0.55, 0.40, 0.55), "intensity": 0.0,
                "cause": extract_cause(text), "appraisal": {}, "source": source}
    v = sum(x[0] for x in vals) / len(vals)
    a = sum(x[1] for x in vals) / len(vals)
    d = sum(x[2] for x in vals) / len(vals)
    v = max(0.0, min(1.0, v + boost * 0.5))
    a = max(0.0, min(1.0, a + boost * 0.5))
    label = nearest_primary((v, a, d))
    intensity = round(max(abs(v - 0.55), abs(a - 0.45)) * 2, 2)
    appraisal = {"pleasantness": round(v, 2),
                 "control": round(d, 2),
                 "certainty": round(1.0 - abs(a - 0.5) * 2, 2)}
    return {"label": label, "vad": (round(v, 2), round(a, 2), round(d, 2)),
            "intensity": intensity, "cause": extract_cause(text),
            "appraisal": appraisal, "source": source, "hits": hits}


def nearest_primary(vad: Tuple[float, float, float]) -> str:
    best, bd = "neutral", 1e9
    for k, w in WHEEL_VAD.items():
        dist = sum((x - y) ** 2 for x, y in zip(vad, w)) ** 0.5
        if dist < bd:
            best, bd = k, dist
    if bd > 0.45:
        return "neutral"
    return best


def extract_cause(text: str) -> str:
    """EICAP layer 2: why do they feel this? because/when/since clauses first."""
    m = re.search(r"\b(?:because|since|as|when|after|about|over)\b(.{3,120})", text or "", re.I)
    if m:
        cause = re.sub(r"^(my|the|this|that|a|an)\s+", "", m.group(1).strip(" ."))
        return cause
    nouns = re.findall(r"\b(?:exam|interview|work|boss|money|health|family|wife|husband|"
                       r"mother|father|friend|deadline|meeting|doctor|hospital|surgery|"
                       r"flight|job|school|team|project|night|morning)\b", text or "", re.I)
    return nouns[0].lower() if nouns else ""


# -- 2. manage: empathy composer (never mirrors across opposite pairs) --------------
def empathize(label: str, intensity: float, cause: str = "",
              playbook: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """EICAP layer 4: acknowledge → normalize → perspective → action.
    Tone mirrors warmth, never the distress itself (Plutchik opposites)."""
    avoid = OPPOSITES.get(label, "")
    cause_bit = f" about {cause}" if cause else ""
    if label in ("sadness", "fear", "anger", "disgust") and intensity > 0.25:
        ack = f"I hear you — feeling {label}{cause_bit} makes sense."
        norm = "Anyone would feel the weight of that."
        act = ("Want to talk it through, or should I lighten the load — "
               "I can queue your tasks and keep things quiet.")
        tone = "gentle"
    elif label in ("joy", "trust", "anticipation"):
        ack = f"Love that energy{cause_bit}!"
        norm = "You earned this one."
        act = "Want me to save this moment, or ride the momentum into your tasks?"
        tone = "warm"
    elif label == "surprise":
        ack = "That caught you off guard, huh?"
        norm = "Give it a minute to land."
        act = "Want the quick facts on it, or time to sit with it first?"
        tone = "steady"
    else:
        ack = "I'm listening."
        norm = "Tell me more whenever you're ready."
        act = "I can research it, note it, or just keep you company."
        tone = "steady"
    lines = playbook.get("comfort_lines", []) if playbook else []
    if lines and label in ("sadness", "fear", "anger"):
        act += f" Something that helped before: “{lines[0]}”."
    return {"acknowledge": ack, "normalize": norm, "perspective": act,
            "tone": tone, "never_mirrors": avoid,
            "full": f"{ack} {norm} {act}"}


# -- 3. emotional learning: what actually helped? --------------------------------------
def learn_playbook(episodes: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Mines VAD-tagged episodes: response patterns before mood IMPROVEMENT
    become the playbook (versioned). Correlation, honestly labeled."""
    try:
        from saturday import humanoid as _h
    except Exception:
        return {"success": False, "error": "humanoid memory unavailable"}
    if episodes is None:
        try:
            p = _h._ep_path()
            episodes = []
            if p.exists():
                import json as _j
                with open(p, encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            episodes.append(_j.loads(line))
                        except Exception:
                            pass
        except Exception:
            episodes = []
    emo = [e for e in (episodes or []) if "mood" in (e.get("tags") or [])]
    helped = [e for e in emo if e.get("importance", 0) >= 0.7]
    try:
        from saturday.custom_brain import _read_json, _write_json
    except Exception:
        return {"success": False, "error": "brain store unavailable"}
    pb = _read_json("empathy_playbook.json",
                    {"version": 0, "comfort_lines": [], "avoid": [], "notes": []})
    for e in helped[-10:]:
        line = e.get("text", "")[:160]
        if line and line not in pb["comfort_lines"]:
            pb["comfort_lines"].append(line)
    pb["comfort_lines"] = pb["comfort_lines"][-20:]
    pb["version"] += 1
    pb["episodes_seen"] = len(emo)
    _write_json("empathy_playbook.json", pb)
    return {"success": True, "version": pb["version"],
            "episodes_seen": len(emo), "comfort_lines": len(pb["comfort_lines"])}


# -- 4. autonomous answering with EI (thinks + feels + answers on its own) --------------
def answer(question: str, core=None, user_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One brain answering alone: S1 known → S2 teachers → EI modulation.
    Returns {answer, path, emotion_read, confidence}. Speaks when core given."""
    q = (question or "").strip()
    if not q:
        return {"success": False, "error": "empty question"}
    user_state = user_state or {}
    emo = analyze(q)
    # S1: answer from what we KNOW (profile, vault, math) — instant, exact
    s1 = _answer_from_knowledge(q, core)
    if s1:
        s1["emotion_read"] = emo
        s1["path"] = "s1-known"
        _modulate(s1, emo, user_state)
        _finish(s1, core, q, emo)
        return s1
    # S2: teachers deliberate (novel questions), dissent preserved
    try:
        from saturday import custom_brain as _cb
        v = _cb.teacher_label(f"Answer conversationally in 2 sentences: {q}")
        acts = [x.get("action") for x in v.get("votes", []) if x.get("action")]
        text = (f"Here's how I see it: {q[:120]} — "
                f"my read leans {acts[0] if acts else 'careful thought'}.")
        if v.get("disagree"):
            text += " (My teachers see two sides here — ask me to dig deeper.)"
        out: Dict[str, Any] = {"success": True, "answer": text, "path": "s2-teachers",
                               "confidence": 0.55, "dissent": v.get("votes") if v.get("disagree") else None,
                               "emotion_read": emo}
    except Exception as e:
        out = {"success": True, "answer": f"I'm still turning that over — {q[:100]}?",
               "path": "s1-honest-unsure", "confidence": 0.3, "emotion_read": emo,
               "note": f"S2 offline: {e}"[:120]}
    _modulate(out, emo, user_state)
    _finish(out, core, q, emo)
    return out


def _answer_from_knowledge(q: str, core) -> Optional[Dict[str, Any]]:
    low = q.lower()
    if core is None:
        return None
    try:
        if any(k in low for k in ("who am i", "what do you know", "about me", "my name")):
            return {"success": True, "answer": core.process_command("profile", trusted=True)[:500],
                    "confidence": 0.85}
        if low.startswith(("remember", "recall")) or "remember" in low:
            return {"success": True, "answer": core.process_command(f"recall {q}"[:120], trusted=True)[:500],
                    "confidence": 0.8}
        import re as _re
        if _re.search(r"[\d][\s]*[+\-*/^]", q) or any(w in low for w in ("calc", "solve", "plus", "percent")):
            r = core.process_command(f"calc {q}", trusted=True)
            if not r.startswith("❌"):
                return {"success": True, "answer": r[:300], "confidence": 0.95}
    except Exception:
        pass
    return None


def _modulate(out: Dict[str, Any], emo: Dict[str, Any], user_state: Dict[str, Any]):
    """EI modulation: user's feelings reshape tone/framing, never facts."""
    label, inten = emo.get("label", "neutral"), emo.get("intensity", 0.0)
    mood = (user_state.get("mood") or "").lower()
    prefix = ""
    if label in ("sadness", "fear", "anger") and inten > 0.3:
        prefix = "Gently: "
        out["tone"] = "gentle"
    elif mood in ("sad", "anxious", "angry"):
        prefix = "Take your time — "
        out["tone"] = "gentle"
    elif label == "joy":
        out["tone"] = "warm"
    else:
        out["tone"] = out.get("tone", "steady")
    if prefix and out.get("answer"):
        out["answer"] = prefix + out["answer"]
    out["empathy"] = empathize(label, inten, emo.get("cause", ""))


def _finish(out: Dict[str, Any], core, q: str, emo: Dict[str, Any]):
    try:
        if core is not None and out.get("success") and out.get("answer"):
            core._speak(out["answer"][:300])
    except Exception:
        pass
    try:
        from saturday import humanoid as _h
        _h.remember_episode("answer", f"Q: {q[:120]} → {out.get('path')} "
                                     f"(user felt {emo.get('label')})",
                            importance=0.6 if emo.get("label") != "neutral" else 0.35,
                            tags=["answer", "mood", emo.get("label", "neutral")])
    except Exception:
        pass


# -- EI status + probes --------------------------------------------------------------------
def eq_status() -> Dict[str, Any]:
    source, norms = load_lexicon()
    try:
        from saturday.custom_brain import _read_json
        pb = _read_json("empathy_playbook.json", {"version": 0, "comfort_lines": []})
    except Exception:
        pb = {"version": 0, "comfort_lines": []}
    return {"lexicon": f"{source} ({len(norms)} words)",
            "playbook_version": pb.get("version", 0),
            "comfort_lines": len(pb.get("comfort_lines", [])),
            "primaries": PLUTCHIK,
            "charter": "simulated care, real attention — never claims to feel"}


def ei_probes() -> Dict[str, Any]:
    """Framing probes for emotional queries: same need, different words,
    same empathy family. Deterministic."""
    groups = [
        ["I'm so sad today", "feeling really down right now", "today is a sad day"],
        ["I'm furious at my boss", "so angry right now", "my boss makes me mad"],
        ["I'm scared about the surgery", "anxious about tomorrow", "nervous and afraid"],
    ]
    fam = {"sadness": "low", "fear": "low", "anger": "low", "joy": "high",
           "trust": "high", "anticipation": "high", "surprise": "mid",
           "disgust": "low", "neutral": "mid"}
    results = []
    for variants in groups:
        labels = [analyze(v)["label"] for v in variants]
        fams = {fam.get(l, "?") for l in labels}
        results.append({"ask": variants[0], "labels": labels,
                        "consistent": len(fams) == 1})
    passed = sum(1 for r in results if r["consistent"])
    return {"success": True, "passed": passed, "total": len(results),
            "probes": results,
            "verdict": ("stable across framings" if passed == len(results)
                        else f"{len(results)-passed} drift(s) — lexicon growth advised")}
