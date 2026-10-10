"""SATURDAY Humanoid — THE ADVANCED HUMANOID BRAIN: human-like + machine-exact.

Science it's built on (not slogans — mechanisms from the literature):
  SOFAI (Nature 2025) ...... S1 fast solvers + S2 slow solvers + METACOGNITIVE
                             arbiter (confidence × cost × stakes). S1 fires by
                             default; S2 only when metacognition calls it.
  DPT-Agent (ACL 2025) ..... Theory-of-Mind (infer the human's intent/beliefs
                             from history) + async reflection + S2 guidelines
                             steering S1 (our mined skills).
  Global Workspace (IEEE).. working memory with decaying strength →
                             EPISODIC memory on context change; one broadcast
                             channel all specialists read.
  ACT-R + humanoids ....... declarative chunks retrieved to augment the LLM
                             prompt; procedural skills execute.

Mapping onto real code here:
  System 1 (fast, Ollama-free) .... CustomBrain: skills + intent + TF-IDF (<0.1s)
  System 2 (slow, deliberative) ... llama3.2 + qwen2.5 debate, moondream sight,
                                    sympy proof for math (minutes, thorough)
  Metacognition ................... Arbiter: confidence × stakes × resources
  Episodic memory ................. vault/file episodes w/ importance + decay
  Working memory .................. bounded goal stack + attentional broadcast
  Theory of Mind .................. user model: facts, habits, inferred intent
  Drives (machine-readable mood) .. focus/load/mood → modulate plans honestly
  Sleep ........................... learn(): consolidate S1+S2+episodes (via
                                    custom_brain.learn + episodic prune)

Human where it matters (intent, memory, caution, tone), machine where it
counts (math exact, tools deterministic, every call audited). Import-light:
heavy deps load lazily; the arbiter + memory math is pure stdlib/sklearn.
"""

import json
import logging
import re
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("SATURDAY.Humanoid")

try:
    from saturday.custom_brain import BRAIN_DIR, _read_json, _write_json
except Exception:  # standalone-safe defaults
    import os as _os
    BRAIN_DIR = Path(_os.getenv("SATURDAY_BRAIN_DIR",
                                r"D:\S.A.T.U.R.D.A.Y\models\custom_brain"))

    def _read_json(name, default):
        try:
            p = BRAIN_DIR / name
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default

    def _write_json(name, data):
        try:
            BRAIN_DIR.mkdir(parents=True, exist_ok=True)
            (BRAIN_DIR / name).write_text(json.dumps(data), encoding="utf-8")
        except Exception as e:
            logger.warning(f"humanoid write failed: {e}")

S1_CONFIDENT = 0.55   # at/above: System 1 may act alone
S2_CONFIDENT = 0.80   # below this + high stakes: deliberate or ask


# -- stakes: what makes a goal deserve slow thinking ------------------------------
try:
    from saturday.agent import DESTRUCTIVE_BITS as _DBITS
except Exception:
    _DBITS = ("delete", "format", "shutdown", "purchase", "pay ")
HIGH_STAKES_HINTS = _DBITS + ("send", "publish", "share", "cloud",
                              "password", "payment", "irreversible")


def estimate_stakes(goal: str) -> Dict[str, Any]:
    g = (goal or "").lower()
    hits = [h for h in HIGH_STAKES_HINTS if h in g]
    level = "high" if hits else ("medium" if len(g.split()) > 12 else "low")
    return {"level": level, "triggers": hits[:4]}


# -- metacognitive arbiter (SOFAI-style: confidence × cost × stakes) ------------------
def arbitrate(s1_intent: str, s1_conf: float, stakes: str,
              s2_available: bool, time_budget_s: float = 300.0) -> Dict[str, Any]:
    """Pure function, fully tested. Returns path + reason (audit trail)."""
    if stakes == "high" and s1_conf < S2_CONFIDENT:
        if s2_available:
            return {"path": "deliberate",
                    "reason": f"high stakes + S1 {s1_conf:.0%} < {S2_CONFIDENT:.0%} → slow teachers"}
        return {"path": "ask",
                "reason": "high stakes, S1 unsure, no S2 online → ask human"}
    if s1_conf >= S1_CONFIDENT:
        return {"path": "act",
                "reason": f"S1 {s1_conf:.0%} ≥ {S1_CONFIDENT:.0%} → fast skills"}
    if s2_available and time_budget_s >= 60:
        return {"path": "deliberate",
                "reason": f"S1 unsure ({s1_conf:.0%}) + time → slow teachers"}
    if s1_conf >= 0.30:
        return {"path": "act_cautious",
                "reason": f"S1 weak ({s1_conf:.0%}) but no S2/time → verify-each-step"}
    return {"path": "ask", "reason": f"S1 {s1_conf:.0%} too low → ask human"}


# -- working memory: bounded stack + broadcast ----------------------------------------
class WorkingMemory:
    """Holds the now: current goal, salient entities, last results.
    Strength decays (GWT); broadcast() builds the one context line every
    specialist (prompts, ToM, drives) reads."""

    def __init__(self, capacity: int = 7):
        self.items: deque = deque(maxlen=capacity)

    def push(self, kind: str, text: str, strength: float = 5.0):
        self.items.append({"t": time.time(), "kind": kind,
                           "text": text[:300], "strength": strength})

    def decay(self, half_life_s: float = 300.0):
        now = time.time()
        for it in self.items:
            it["strength"] *= 0.5 ** ((now - it["t"]) / half_life_s)
        self.items = deque([i for i in self.items if i["strength"] > 0.5],
                           maxlen=self.items.maxlen)

    def broadcast(self) -> str:
        self.decay()
        top = sorted(self.items, key=lambda i: -i["strength"])[:4]
        if not top:
            return "working-memory: empty (fresh mind)"
        return "working-memory: " + " | ".join(
            f"[{i['kind']}] {i['text'][:80]}" for i in top)


# -- episodic memory: importance-scored, decaying, consolidated in sleep ---------------
def _ep_path() -> Path:
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    return BRAIN_DIR / "episodes.jsonl"


def remember_episode(kind: str, text: str, importance: float = 0.5,
                     tags: Optional[List[str]] = None) -> None:
    """Importance: success/novelty/emotion-weighted by the caller (0..1)."""
    try:
        with open(_ep_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), "kind": kind,
                                 "text": text[:500],
                                 "importance": max(0.0, min(1.0, importance)),
                                 "tags": tags or []}) + "\n")
    except Exception as e:
        logger.warning(f"episode store failed: {e}")


def recall_episodes(query: str, top: int = 3) -> List[Dict[str, Any]]:
    """Recency × importance × TF-IDF match. Pure retrieval, no LLM."""
    try:
        eps = []
        p = _ep_path()
        if p.exists():
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        eps.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        return []
    if not eps or not query.strip():
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        texts = [e["text"] for e in eps]
        sims = cosine_similarity(
            TfidfVectorizer().fit_transform(texts + [query])[len(texts):],
            TfidfVectorizer().fit_transform(texts + [query])[:len(texts)])[0]
    except Exception:
        sims = [0.0] * len(eps)
    now = time.time()
    scored = []
    for e, s in zip(eps, sims):
        age_h = (now - e.get("t", now)) / 3600.0
        recency = 1.0 / (1.0 + age_h / 24.0)
        score = 0.5 * float(s) + 0.3 * e.get("importance", 0.5) + 0.2 * recency
        scored.append((score, e))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [{"text": e["text"][:220], "kind": e.get("kind", ""),
             "score": round(s, 3)} for s, e in scored[:top]]


def consolidate_episodes(max_keep: int = 2000) -> Dict[str, Any]:
    """Sleep work: drop trivial + decayed, merge near-duplicates. Returns diff."""
    p = _ep_path()
    if not p.exists():
        return {"kept": 0, "dropped": 0, "merged": 0}
    eps = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            try:
                eps.append(json.loads(line))
            except Exception:
                pass
    now = time.time()
    kept, dropped, merged = [], 0, 0
    seen = set()
    for e in sorted(eps, key=lambda x: -x.get("t", 0)):
        age_d = (now - e.get("t", now)) / 86400.0
        if e.get("importance", 0.5) < 0.15 and age_d > 7:
            dropped += 1
            continue
        sig = re.sub(r"\d+", "#", e.get("text", "").lower()[:60])
        if sig in seen:
            merged += 1
            continue
        seen.add(sig)
        kept.append(e)
    kept = kept[:max_keep]
    with open(p, "w", encoding="utf-8") as fh:
        for e in kept:
            fh.write(json.dumps(e) + "\n")
    return {"kept": len(kept), "dropped": dropped, "merged": merged}


# -- theory of mind: a working model of YOU ---------------------------------------------
def update_user_model(cmd_counts: Optional[Dict[str, int]] = None,
                      profile_facts: Optional[List[str]] = None,
                      mood: Optional[str] = None) -> Dict[str, Any]:
    """Build/refresh the believed model of the human from real traces."""
    m = _read_json("user_model.json", {"sightings": 0, "top_commands": {},
                                       "facts": [], "beliefs": {}})
    if cmd_counts:
        tc = m.setdefault("top_commands", {})
        for k, v in cmd_counts.items():
            tc[k] = tc.get(k, 0) + v
    if profile_facts:
        facts = m.setdefault("facts", [])
        for f in profile_facts[:20]:
            if f not in facts:
                facts.append(f)
    tops = sorted(m.get("top_commands", {}).items(), key=lambda kv: -kv[1])[:3]
    beliefs = {
        "power_user": sum(m.get("top_commands", {}).values()) > 50,
        "builder": any(k in m.get("top_commands", {}) for k in ("forge", "imagine", "evolve")),
        "researcher": any(k in m.get("top_commands", {}) for k in ("research", "nsearch", "brain")),
        "current_mood": mood or m.get("beliefs", {}).get("current_mood", "unknown"),
        "top_commands": [k for k, _ in tops],
    }
    m["beliefs"] = beliefs
    m["sightings"] = m.get("sightings", 0) + 1
    _write_json("user_model.json", m)
    return beliefs


def infer_intent(goal: str, beliefs: Dict[str, Any]) -> str:
    """ToM-guided reading: same words, different likely need per user type."""
    g = goal.lower()
    if beliefs.get("builder") and any(w in g for w in ("make", "build", "create")):
        return "wants a 3D artifact (forge first, then show render)"
    if beliefs.get("researcher") and any(w in g for w in ("find", "what", "why", "how")):
        return "wants researched facts, vaulted (nsearch first)"
    return "wants the direct action the words name"


# -- drives: machine-readable emotion → plan modulation -----------------------------------
def drives_from_state(focus: Optional[float] = None, load: Optional[float] = None,
                      mood: Optional[str] = None) -> Dict[str, Any]:
    """Human feeling → machine modulation. Documented, bounded, overridable."""
    d: Dict[str, Any] = {"tone": "steady", "pace": "normal", "defer": []}
    if (load or 0) >= 70:
        d["tone"] = "calm-brief"
        d["pace"] = "gentle-single-steps"
        d["defer"].append("non-urgent announcements held until load drops")
    if (focus or 0) >= 70:
        d["pace"] = "protective-quiet"
        d["defer"].append("background chatter suppressed during deep focus")
    if (mood or "").lower() in ("sad", "anxious", "angry"):
        d["tone"] = "gentle"
        d["defer"].append("criticism softened; encouragement first")
    if (mood or "").lower() == "happy":
        d["tone"] = "warm"
    return d


# -- the humanoid think cycle ---------------------------------------------------------------
def think(goal: str,
          s1: Optional[Callable[[str], Tuple[str, float]]] = None,
          s2: Optional[Callable[[str, str], Dict[str, Any]]] = None,
          beliefs: Optional[Dict[str, Any]] = None,
          drives: Optional[Dict[str, Any]] = None,
          wm: Optional[WorkingMemory] = None,
          time_budget_s: float = 300.0) -> Dict[str, Any]:
    """One dual-process cycle. s1/s2 injectable → fully testable offline.
    Returns the audit trail: path, action plan, confidences, dissent."""
    goal = (goal or "").strip()
    stakes = estimate_stakes(goal)
    beliefs = beliefs if beliefs is not None else _read_json("user_model.json", {}).get("beliefs", {})
    drives = dict(drives) if drives is not None else {"tone": "steady", "pace": "normal", "defer": []}
    # emotional layer: the goal's own feeling reshapes the plan's tone
    emotion_read: Dict[str, Any] = {}
    try:
        from saturday import emotion as _em
        emotion_read = _em.analyze(goal)
        if emotion_read.get("label") in ("sadness", "fear", "anger", "disgust") \
                and emotion_read.get("intensity", 0) > 0.3:
            drives["tone"] = "gentle"
            drives.setdefault("defer", []).append(
                f"goal carries {emotion_read['label']} — lead with care, facts second")
    except Exception:
        pass
    wm = wm or WorkingMemory()
    wm.push("goal", goal)
    tom_line = infer_intent(goal, beliefs)
    eps = recall_episodes(goal)
    # System 1: fast retrieval (default = our CustomBrain intent)
    if s1 is None:
        def s1(g: str) -> Tuple[str, float]:
            try:
                from saturday import custom_brain as _cb
                r = _cb.predict_intent(g)
                return r["intent"], float(r.get("confidence", 0.0))
            except Exception:
                return "chat", 0.0
    intent, conf = s1(goal)
    route = arbitrate(intent, conf, stakes["level"],
                      s2_available=s2 is not None or _s2_online(),
                      time_budget_s=time_budget_s)
    out: Dict[str, Any] = {"goal": goal, "intent": intent,
                           "s1_confidence": round(conf, 3),
                           "stakes": stakes, "route": route,
                           "tom": tom_line, "drives": drives,
                           "emotion": emotion_read,
                           "episodes_used": [e["text"][:100] for e in eps],
                           "broadcast": wm.broadcast()}
    if route["path"] in ("act", "act_cautious"):
        try:
            from saturday import custom_brain as _cb
            plan = _cb.INTENT_PLANS.get(intent, _cb.INTENT_PLANS["chat"])
            out["plan"] = plan
            out["answer"] = None
        except Exception as e:
            out["plan"] = []
            out["answer"] = f"S1 plan failed: {e}"
    elif route["path"] == "deliberate":
        fn = s2 or _s2_teachers
        verdict = fn(goal, out["broadcast"])
        out["deliberation"] = verdict
        out["plan"] = verdict.get("plan", [])
        out["dissent"] = verdict.get("dissent")
    else:
        out["plan"] = []
        out["answer"] = ("I'm not sure enough for these stakes — "
                         "tell me the first move (or say 'do it anyway').")
    remember_episode("think", f"{goal} → {route['path']} ({intent} {conf:.0%})",
                     importance=0.7 if stakes["level"] == "high" else 0.4,
                     tags=[intent, route["path"]])
    return out


def _s2_online() -> bool:
    try:
        from saturday.brain import OllamaBrain
        return OllamaBrain(timeout=10).available()
    except Exception:
        return False


def _s2_teachers(goal: str, context: str) -> Dict[str, Any]:
    """Slow deliberation: both teachers vote; dissent preserved, never hidden."""
    try:
        from saturday import custom_brain as _cb
        v = _cb.teacher_label(goal, context)
    except Exception as e:
        return {"verdict": "ask", "plan": [], "dissent": f"S2 failed: {e}"}
    try:
        from saturday import neural as _neural
        plan = [{"cmd": s["cmd"], "why": "S2-verdict" + (" (dissent noted)" if v.get("disagree") else "")}
                for s in _neural.route_goal(goal)[:5]]
    except Exception:
        plan = []
    return {"verdict": v.get("winner", "ask"), "plan": plan,
            "dissent": (v["votes"] if v.get("disagree") else None),
            "teachers": [x.get("teacher") for x in v.get("votes", [])]}


def status() -> Dict[str, Any]:
    meta = _read_json("meta.json", {})
    sk = _read_json("skills.json", {"skills": []})
    um = _read_json("user_model.json", {})
    n_ep = 0
    try:
        p = _ep_path()
        if p.exists():
            with open(p, encoding="utf-8") as fh:
                n_ep = sum(1 for _ in fh)
    except Exception:
        pass
    return {"s1": f"intent clf ({meta.get('test_acc', '?')} held-out, "
                  f"{meta.get('samples', 0)} samples, {len(sk.get('skills', []))} skills)",
            "s2": f"teachers {', '.join(['llama3.2', 'qwen2.5:1.5b'])} "
                  f"({'online' if _s2_online() else 'offline'})",
            "episodes": n_ep, "beliefs": um.get("beliefs", {}),
            "sightings": um.get("sightings", 0)}
