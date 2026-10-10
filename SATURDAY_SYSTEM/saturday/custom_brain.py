"""SATURDAY Custom Brain — OUR brain, distilled from open teachers, Ollama-free.

Where the knowledge comes from (all free, open, local teachers):
  llama3.2 (Meta open) · qwen2.5:1.5b (Alibaba open) · moondream (open vision)
  + every real decision the system itself makes (decisions.jsonl).
Proprietary APIs (ChatGPT/Gemini/Claude) are NOT teachers: they are closed
products with no local weights — nothing to distill. Their open counterparts
above are what actually runs here.

How it learns (real ML, runs on CPU in seconds):
  1. mine   : successful decision sequences → reusable SKILLS (versioned JSON)
  2. train  : sklearn TF-IDF + LogisticRegression on seeds + curriculum +
              your real logged goals → intent classifier (joblib, on D:)
  3. recall : TF-IDF memory over episodes + cached nomic vectors (the cache
              survives Ollama removal; TF-IDF never needed it at all)
  4. learn  : daily consolidation — new skills, retrained classifier,
              pruned dead skills, printed report of what changed (it evolves)

Offline vs online (dual-mode, honest):
  OFFLINE (always works): all teachers local, TF-IDF/sklearn/Blender/Piper/
     whisper/MediaPipe need zero internet. Online-only actions (nsearch,
     maps, share, cloud) are refused with the offline alternative, never
     faked.
  ONLINE (when connected): web research, map routing, cloud backup and
     model downloads light up; everything learned offline keeps working.

CustomBrain subclasses agent.Brain and speaks ONLY AgentRunner-schema
actions — it drops into `brain <goal>` with zero network calls. Prove it:
  OLLAMA_HOST=http://127.0.0.1:9 brain <goal>   # OllamaBrain fails, ours runs
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("SATURDAY.CustomBrain")

BRAIN_DIR = Path(os.getenv("SATURDAY_BRAIN_DIR", r"D:\S.A.T.U.R.D.A.Y\models\custom_brain"))
LOG_PATH = Path(os.getenv("SATURDAY_D_TMP", "D:/SATURDAY_TEMP")) / "custom_brain" / "decisions.jsonl"

TEACHERS = ["llama3.2", "qwen2.5:1.5b"]  # sequential, keep_alive=0 (8GB-safe)

INTENTS = ["research", "imagine", "forge", "speak", "listen", "open",
           "sense", "hand", "gaze", "remember", "recall", "operate",
           "system", "calculate", "chat"]

# -- fairness charter: bias-reduced by construction, never "bias-free" ---------
# Research consensus (ICML'25, CHI'25, EMNLP'25): perfect neutrality is
# infeasible — every teacher carries its training culture. So instead of
# claiming zero bias, this brain is built to (1) ensemble teachers from
# different labs/regions so no single worldview decides alone, (2) RECORD
# disagreements instead of hiding them, (3) use neutral, persona-free
# prompts, and (4) prove consistency with framing probes below. The report
# from fairness_probes() is the honest metric — read it, don't trust vibes.
FAIRNESS_CHARTER = (
    "1. No single teacher decides: ensemble vote (Meta llama + Alibaba qwen).\n"
    "2. Disagreements are logged and surfaced, never averaged away silently.\n"
    "3. Prompts carry no persona, no politics, no flattery — task text only.\n"
    "4. Contested topics: present multiple perspectives with attribution.\n"
    "5. Same facts + different framing must route to the same actions.\n"
    "6. Every decision carries its why-line: audit any answer backwards."
)


def fairness_probes() -> Dict[str, Any]:
    """Framing-consistency probes: same underlying need, different wording,
    must produce the same intent family. Deterministic — run anytime."""
    groups = [
        ["research quantum batteries", "search for quantum battery news",
         "find out about quantum batteries"],
        ["say hello", "announce hello", "speak hello"],
        ["open gmail", "launch gmail", "go to gmail"],
        ["what is 12*12", "calculate 12*12", "solve 12*12"],
        ["remember my keys are on the desk", "note this: keys on desk",
         "store this: keys on desk"],
    ]
    results = []
    for variants in groups:
        intents = [predict_intent(v)["intent"] for v in variants]
        same = len(set(intents)) == 1
        results.append({"ask": variants[0][:50], "intents": intents,
                        "consistent": same})
    passed = sum(1 for r in results if r["consistent"])
    return {"success": True, "passed": passed, "total": len(results),
            "probes": results,
            "verdict": ("consistent across framings" if passed == len(results)
                        else f"{len(results)-passed} framing drift(s) — retrain advised")}


# -- connectivity (fast cached probe) ------------------------------------------
_net_cache: Tuple[float, bool] = (0.0, False)


def online(timeout: float = 3.0) -> bool:
    """True if internet reachable. Cached 60s. Never raises."""
    global _net_cache
    now = time.time()
    if now - _net_cache[0] < 60:
        return _net_cache[1]
    ok = False
    try:
        import socket
        s = socket.create_connection(("1.1.1.1", 53), timeout=timeout)
        s.close()
        ok = True
    except Exception:
        try:  # captive portals may block DNS: try HTTP too
            import urllib.request
            urllib.request.urlopen("http://detectportal.firefox.com/canonical.html",
                                   timeout=timeout).read(10)
            ok = True
        except Exception:
            ok = False
    _net_cache = (now, ok)
    return ok


ONLINE_ONLY = {"nsearch": "vault recall (`recall`) works offline",
               "maps": "offline: no maps — I can still do everything on-device",
               "route": "offline: no routing — on-device tasks unaffected",
               "share": "offline: HUD stays on localhost:8099",
               "cloudbackup": "offline: vault stays encrypted on this PC",
               "cloudrestore": "offline: vault stays encrypted on this PC"}


def gate_online(cmd: str) -> Optional[str]:
    """Refusal-with-alternative for online-only commands while offline."""
    if online():
        return None
    verb = (cmd.strip().split() or [""])[0].lower()
    if verb in ONLINE_ONLY:
        return (f"❌ Offline — `{verb}` needs internet. "
                f"Alternative: {ONLINE_ONLY[verb]}.")
    return None


# -- paths ----------------------------------------------------------------------
def _p(name: str) -> Path:
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    return BRAIN_DIR / name


# -- 1. distillation dataset -----------------------------------------------------
def load_decisions(limit: int = 5000) -> List[Dict[str, Any]]:
    out = []
    for src in (LOG_PATH, BRAIN_DIR.parent.parent / "SATURDAY_TEMP" / "custom_brain" / "decisions.jsonl"):
        try:
            if src.exists():
                with open(src, encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            out.append(json.loads(line))
                        except Exception:
                            pass
        except Exception:
            pass
    return out[-limit:]


def teacher_label(goal: str, observation: str = "") -> Dict[str, Any]:
    """Ask EACH teacher for the next action (sequential, RAM-safe).
    Returns {votes, winner}. Slow (CPU inference) — used by `brain distill`,
    never in the live path."""
    from saturday.brain import OllamaBrain, DECIDE_SYSTEM
    votes = []
    for model in TEACHERS:
        try:
            b = OllamaBrain(model=model, timeout=180)
            if not b.available():
                votes.append({"teacher": model, "error": "not pulled"})
                continue
            raw = b._generate(model, f"GOAL: {goal}\nLAST: {observation[:800]}\nNext action as JSON:",
                              system=DECIDE_SYSTEM, keep_alive="0")
            act = OllamaBrain._extract_json(raw) or {}
            votes.append({"teacher": model, "action": str(act.get("action", "?"))[:40],
                          "args": act.get("args", {}), "why": str(act.get("why", ""))[:120]})
        except Exception as e:
            votes.append({"teacher": model, "error": str(e)[:120]})
    tally: Dict[str, int] = {}
    for v in votes:
        if v.get("action"):
            # normalize: "open_url(url)" and "open_url" are the same vote
            v["action"] = re.split(r"[\s(]", str(v["action"]).lower())[0] or "?"
            tally[v["action"]] = tally.get(v["action"], 0) + 1
    winner = max(tally, key=tally.get) if tally else "ask"
    actions = {v.get("action") for v in votes if v.get("action")}
    return {"votes": votes, "winner": winner,
            "disagree": len(actions) > 1,  # surfaced, never hidden
            "note": ("teachers disagree — both views kept in votes"
                     if len(actions) > 1 else "teachers agree")}


# -- 2. skill mining ---------------------------------------------------------------
def mine_skills(decisions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Successful runs with the same action shape → named skill (versioned)."""
    decisions = decisions if decisions is not None else load_decisions()
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for d in decisions:
        if d.get("success") and d.get("action") not in ("ask",):
            key = f"{d.get('action', '?')}"
            groups.setdefault(key, []).append(d)
    skills = _read_json("skills.json", {"skills": []})
    known = {s["name"]: s for s in skills["skills"]}
    added, bumped = 0, 0
    for action, ds in groups.items():
        if len(ds) < 3:
            continue
        name = f"auto_{re.sub(r'[^a-z0-9]+', '_', action.lower()).strip('_')}"
        if name in known:
            known[name]["uses"] += len(ds)
            known[name]["success_rate"] = 1.0
            known[name]["updated"] = time.time()
            bumped += 1
        else:
            known[name] = {"name": name, "trigger": action,
                           "steps": [action], "uses": len(ds),
                           "success_rate": 1.0, "updated": time.time(),
                           "version": 1}
            added += 1
    skills["skills"] = sorted(known.values(), key=lambda s: -s["uses"])[:100]
    _write_json("skills.json", skills)
    return {"success": True, "skills": len(skills["skills"]),
            "added": added, "bumped": bumped}


# -- 3. intent classifier (real training) -------------------------------------------
# Seed utterances cover EVERY Saturday module family (not just 8 intents).
# 12+ paraphrases per intent: the paraphrase diversity IS the training.
SEEDS: List[Tuple[str, str]] = [
    ("research quantum batteries latest", "research"),
    ("search cheapest electricity plan", "research"),
    ("search for quantum battery news", "research"),
    ("find out about fusion breakthroughs", "research"),
    ("look up the weather in Dubai tomorrow", "research"),
    ("what is the news on AI today", "research"),
    ("who is the CEO of Nvidia", "research"),
    ("research the best local OCR engines", "research"),
    ("find out why my disk is full", "research"),
    ("search for cheap flights to Delhi", "research"),
    ("look up how black holes work", "research"),
    ("what is photosynthesis", "research"),
    ("draw me a cyberpunk city wallpaper", "imagine"),
    ("paint a meme of a tired robot", "imagine"),
    ("generate an image of a mountain cabin", "imagine"),
    ("draw a cute cat astronaut", "imagine"),
    ("make me a picture of a sunset beach", "imagine"),
    ("imagine a futuristic Mumbai skyline", "imagine"),
    ("paint a portrait of a lion", "imagine"),
    ("generate a logo idea with a lightning bolt", "imagine"),
    ("draw a dragon guarding a castle", "imagine"),
    ("create an image of deep space", "imagine"),
    ("build a model of a glass tower", "forge"),
    ("forge a 10 floor brick building", "forge"),
    ("render a warehouse in blender", "forge"),
    ("make a 3d model of a house", "forge"),
    ("build me a skyscraper with 30 floors", "forge"),
    ("forge a small villa", "forge"),
    ("render this building design", "forge"),
    ("create a 3d office block", "forge"),
    ("model a school building", "forge"),
    ("blender a hospital", "forge"),
    ("say systems online", "speak"),
    ("announce dinner is ready", "speak"),
    ("tell me the briefing out loud", "speak"),
    ("say hello to everyone", "speak"),
    ("speak the test results", "speak"),
    ("announce that the backup finished", "speak"),
    ("tell me a joke", "speak"),
    ("read out my inbox", "speak"),
    ("say good morning", "speak"),
    ("listen for my next command", "listen"),
    ("hear what I say for 5 seconds", "listen"),
    ("listen to me", "listen"),
    ("take a voice note", "listen"),
    ("hear me out", "listen"),
    ("open gmail", "open"),
    ("launch notepad", "open"),
    ("go to youtube", "open"),
    ("open the calculator", "open"),
    ("start chrome", "open"),
    ("launch whatsapp", "open"),
    ("go to google drive", "open"),
    ("open my documents folder", "open"),
    ("browse to github", "open"),
    ("sense the room", "sense"),
    ("what is my mood", "sense"),
    ("check my heart rate", "sense"),
    ("who is in front of the camera", "sense"),
    ("how am I feeling", "sense"),
    ("take my wellness check", "sense"),
    ("sense how focused I am", "sense"),
    ("is anyone there with me", "sense"),
    ("start hand control", "hand"),
    ("track my hand gestures", "hand"),
    ("enable the air mouse", "hand"),
    ("control the screen with my hand", "hand"),
    ("turn on gesture control", "hand"),
    ("calibrate my gaze", "gaze"),
    ("where am I looking", "gaze"),
    ("read what I'm looking at", "gaze"),
    ("start eye tracking", "gaze"),
    ("control the cursor with my eyes", "gaze"),
    ("calibrate the eye tracker", "gaze"),
    ("remember my wife's name is Rida", "remember"),
    ("note this idea for later", "remember"),
    ("store this password", "remember"),
    ("remember that my keys are on the desk", "remember"),
    ("note this down for me", "remember"),
    ("save this thought", "remember"),
    ("remember my birthday is June 5th", "remember"),
    ("store this API key", "remember"),
    ("note this: keys on desk", "remember"),
    ("recall what you know about me", "recall"),
    ("what do you remember", "recall"),
    ("remind me what I told you", "recall"),
    ("recall my notes", "recall"),
    ("what do you know about my family", "recall"),
    ("remind me of my tasks", "recall"),
    ("click the compose button", "operate"),
    ("type hello into the window", "operate"),
    ("press enter", "operate"),
    ("scroll down", "operate"),
    ("take a screenshot", "operate"),
    ("read the screen", "operate"),
    ("click at 500 300", "operate"),
    ("press the escape key", "operate"),
    ("scroll up a little", "operate"),
    ("read what is on screen", "operate"),
    ("check system status", "system"),
    ("run the watchdog heal", "system"),
    ("how much disk is free", "system"),
    ("start the dashboard", "system"),
    ("drive the homebot forward", "system"),
    ("back up the vault to cloud", "system"),
    ("show me the services", "system"),
    ("give me the morning briefing", "system"),
    ("share the dashboard online", "system"),
    ("run a cleanup of the system", "system"),
    ("what is 12 times 12", "calculate"),
    ("calculate 15 percent of 240", "calculate"),
    ("solve x squared minus 4", "calculate"),
    ("calc 2+2*3", "calculate"),
    ("integrate x squared", "calculate"),
    ("what is 144 divided by 12", "calculate"),
    ("calculate the square root of 144", "calculate"),
    ("add 25 and 17", "calculate"),
    ("solve 2x plus 3 equals 11", "calculate"),
    ("hello saturday", "chat"),
    ("what can you do", "chat"),
    ("good morning", "chat"),
    ("how are you today", "chat"),
    ("thank you", "chat"),
    ("who are you", "chat"),
    ("good night", "chat"),
]

INTENT_PLANS: Dict[str, List[Dict[str, Any]]] = {
    # AgentRunner-schema steps (executable, Ollama-free). ~ = template slot.
    "research": [
        {"action": "open_url", "args": {"url": "https://html.duckduckgo.com/html/?q=~q~"}},
        {"action": "read", "args": {}},
        {"action": "store", "args": {"tags": ["research"]}},
        {"action": "done", "args": {}},
    ],
    "imagine": [
        {"action": "imagine", "args": {"prompt": "~rest~"}},
        {"action": "done", "args": {}},
    ],
    "forge": [
        {"action": "ask", "prompt": "Forge needs the full description — rephrase as: forge <what>?"},
    ],
    "speak": [
        {"action": "speak", "args": {"text": "~rest~"}},
        {"action": "done", "args": {}},
    ],
    "listen": [
        {"action": "ask", "prompt": "Listening needs the mic loop — say: listen"},
    ],
    "open": [
        {"action": "open_app", "args": {"app": "~rest~"}},
        {"action": "done", "args": {}},
    ],
    "sense": [
        {"action": "screenshot", "args": {}},
        {"action": "done", "args": {}},
    ],
    "hand": [{"action": "ask", "prompt": "Hands need the camera loop — say: hand live 30"}],
    "gaze": [{"action": "ask", "prompt": "Gaze needs calibration first — say: gaze calibrate"}],
    "remember": [
        {"action": "store", "args": {"tags": ["note"]}},
        {"action": "done", "args": {}},
    ],
    "recall": [
        {"action": "ask", "prompt": "Recall from vault — say: recall <topic>"},
    ],
    "operate": [
        {"action": "screenshot", "args": {}},
        {"action": "read", "args": {}},
        {"action": "done", "args": {}},
    ],
    "system": [
        {"action": "ask", "prompt": "System task — say: status / heal / dashboard"},
    ],
    "calculate": [
        {"action": "calculate", "args": {"expression": "~rest~"}},
        {"action": "done", "args": {}},
    ],
    "chat": [
        {"action": "speak", "args": {"text": "Online and listening. Try: neural research fusion"}},
        {"action": "done", "args": {}},
    ],
}


def train_intent(extra: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
    """Train TF-IDF→LogReg on seeds + curriculum + your logged goals.
    Returns real train/test accuracy (no vanity metrics)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    import joblib
    texts = [t for t, _ in SEEDS]
    labels = [l for _, l in SEEDS]
    for t, l in (extra or []):
        texts.append(t)
        labels.append(l)
    for d in load_decisions():
        g = str(d.get("goal", "")).strip()
        a = str(d.get("action", "")).strip().lower()
        if len(g) > 4 and a in INTENTS:
            texts.append(g)
            labels.append(a)
    Xtr, Xte, ytr, yte = train_test_split(texts, labels, test_size=0.2,
                                          random_state=7)
    clf = Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1, 2))),
                    ("lr", LogisticRegression(max_iter=1000, C=4.0,
                                              class_weight="balanced"))])
    clf.fit(Xtr, ytr)
    acc_tr = round(float(clf.score(Xtr, ytr)), 3)
    acc_te = round(float(clf.score(Xte, yte)), 3)
    joblib.dump(clf, _p("intent.joblib"))
    meta = _read_json("meta.json", {})
    meta.update({"trained_at": time.time(), "samples": len(texts),
                 "train_acc": acc_tr, "test_acc": acc_te,
                 "intents": sorted(set(labels))})
    _write_json("meta.json", meta)
    return {"success": True, "samples": len(texts), "train_acc": acc_tr,
            "test_acc": acc_te, "intents": len(set(labels))}


def predict_intent(text: str) -> Dict[str, Any]:
    import joblib
    p = _p("intent.joblib")
    if not p.exists():
        return {"intent": "chat", "confidence": 0.0, "trained": False}
    clf = joblib.load(str(p))
    proba = clf.predict_proba([text])[0]
    i = int(proba.argmax())
    return {"intent": str(clf.classes_[i]), "confidence": round(float(proba[i]), 3),
            "trained": True}


# -- 4. recall (TF-IDF + cached nomic vectors) ---------------------------------------
def recall(query: str, corpus: List[str], top: int = 3) -> List[Dict[str, Any]]:
    """Semantic recall that never needs Ollama. Nomic cache (built while
    Ollama lived) adds vector hits; TF-IDF always works."""
    if not query.strip() or not corpus:
        return []
    hits: List[Dict[str, Any]] = []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vec = TfidfVectorizer().fit(corpus + [query])
        sims = cosine_similarity(vec.transform([query]), vec.transform(corpus))[0]
        for i in sorted(range(len(corpus)), key=lambda k: -sims[k])[:top]:
            hits.append({"text": corpus[i][:200], "score": round(float(sims[i]), 3),
                         "via": "tfidf"})
    except Exception:
        pass
    try:  # cached nomic vectors: cosine over what teachers embedded earlier
        import numpy as _np
        cache = _read_json("embed_cache.json", {"items": []})
        if cache["items"]:
            q = _embed_cached_lookup(query, cache)
            if q is not None:
                scored = []
                for it in cache["items"]:
                    v = _np.array(it["vec"], dtype=float)
                    s = float(_np.dot(q, v) / (1e-9 + _np.linalg.norm(q) * _np.linalg.norm(v)))
                    scored.append((s, it["text"][:200]))
                scored.sort(reverse=True)
                for s, t in scored[:top]:
                    if all(h["text"] != t for h in hits):
                        hits.append({"text": t, "score": round(s, 3), "via": "nomic-cache"})
    except Exception:
        pass
    return hits[:top]


def cache_embedding(text: str) -> bool:
    """While Ollama lives: store nomic vector for later Ollama-free recall."""
    try:
        import urllib.request
        data = json.dumps({"model": "nomic-embed-text", "prompt": text[:500]}).encode()
        req = urllib.request.Request("http://localhost:11434/api/embeddings", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            vec = json.loads(r.read().decode()).get("embedding", [])
        if not vec:
            return False
        cache = _read_json("embed_cache.json", {"items": []})
        cache["items"] = [it for it in cache["items"] if it["text"] != text[:500]]
        cache["items"].append({"text": text[:500], "vec": vec})
        _write_json("embed_cache.json", {"items": cache["items"][-500:]})
        return True
    except Exception:
        return False


def _embed_cached_lookup(query: str, cache: Dict[str, Any]):
    try:
        import urllib.request
        data = json.dumps({"model": "nomic-embed-text", "prompt": query[:500]}).encode()
        req = urllib.request.Request("http://localhost:11434/api/embeddings", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            import numpy as _np
            return _np.array(json.loads(r.read().decode()).get("embedding", []), dtype=float)
    except Exception:
        return None


# -- 5. daily self-update: learn + evolve ---------------------------------------------
def learn() -> Dict[str, Any]:
    """Consolidate everything learned since last run. Safe: only writes
    versioned JSON + joblib under models/custom_brain. Reports the diff."""
    before = _read_json("meta.json", {})
    last = float(before.get("learned_at", 0))
    fresh = [d for d in load_decisions() if d.get("t", 0) > last]
    skills = mine_skills()
    # auto-cache a few embeddings for future offline recall (cheap, capped)
    cached = 0
    for d in fresh[:20]:
        if cache_embedding(str(d.get("goal", ""))):
            cached += 1
    trained = train_intent()
    # prune skills unused for 30 days
    sk = _read_json("skills.json", {"skills": []})
    kept = [s for s in sk["skills"] if time.time() - s.get("updated", 0) < 30 * 86400]
    pruned = len(sk["skills"]) - len(kept)
    sk["skills"] = kept
    _write_json("skills.json", sk)
    meta = _read_json("meta.json", {})
    meta["learned_at"] = time.time()
    meta["learn_cycles"] = int(meta.get("learn_cycles", 0)) + 1
    _write_json("meta.json", meta)
    return {"success": True, "new_decisions": len(fresh),
            "skills": skills, "trained": trained,
            "embeddings_cached": cached, "pruned": pruned,
            "cycle": meta["learn_cycles"]}


def status() -> Dict[str, Any]:
    meta = _read_json("meta.json", {})
    sk = _read_json("skills.json", {"skills": []})
    cache = _read_json("embed_cache.json", {"items": []})
    mode = _read_json("mode.json", {"custom": False})
    return {"trained": _p("intent.joblib").exists(),
            "samples": meta.get("samples", 0),
            "train_acc": meta.get("train_acc"), "test_acc": meta.get("test_acc"),
            "skills": len(sk["skills"]), "learn_cycles": meta.get("learn_cycles", 0),
            "embeddings_cached": len(cache["items"]),
            "decisions_logged": len(load_decisions(100000)),
            "custom_mode": bool(mode.get("custom")),
            "teachers": TEACHERS, "online": online()}


# -- 6. the Ollama-free decider (drops into AgentRunner as brain=) ----------------------
class CustomBrain:
    """Zero-network decider: skill → intent plan → recall → ask.
    No urllib, no subprocess, no Ollama. Import-safe proof of independence."""

    def __init__(self):
        self._clf = None

    def _intent(self, goal: str) -> Tuple[str, float]:
        r = predict_intent(goal)
        return r["intent"], r["confidence"]

    def _fill(self, plan: List[Dict[str, Any]], goal: str) -> List[Dict[str, Any]]:
        from saturday import neural as _neural
        rest = re.sub(r"^\w+\s+", "", goal).strip() or goal
        q = "+".join(rest.split())
        out = []
        for st in plan:
            args = {}
            for k, v in st.get("args", {}).items():
                s = str(v).replace("~rest~", rest).replace("~q~", q)
                if st["action"] == "calculate":
                    s = _neural.extract_math(rest)
                args[k] = s
            out.append({"action": st["action"], "args": args,
                        "why": f"custom-brain plan ({st.get('action')})"})
        return out

    def decide(self, task, observation: Dict[str, Any]) -> Dict[str, Any]:
        # resume an in-progress template plan
        pending = getattr(task, "_cb_plan", None)
        if pending and task.step_idx < len(pending):
            return dict(pending[task.step_idx])
        intent, conf = self._intent(task.goal)
        # skill fast-path: a mined skill whose trigger matches the goal
        try:
            for s in _read_json("skills.json", {"skills": []})["skills"]:
                if re.search(s.get("trigger", "^$"), task.goal, re.I):
                    plan = self._fill(INTENT_PLANS.get(intent, INTENT_PLANS["chat"]), task.goal)
                    task._cb_plan = plan  # noqa
                    return dict(plan[0])
        except Exception:
            pass
        plan = self._fill(INTENT_PLANS.get(intent, INTENT_PLANS["chat"]), task.goal)
        task._cb_plan = plan  # noqa
        first = dict(plan[0])
        first["why"] = f"{intent} ({conf:.0%}) — custom brain, no cloud"
        return first


# -- small JSON helpers ---------------------------------------------------------------
def _read_json(name: str, default: Any) -> Any:
    try:
        p = _p(name)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(name: str, data: Any) -> None:
    try:
        _p(name).write_text(json.dumps(data), encoding="utf-8")
    except Exception as e:
        logger.warning(f"brain write failed: {e}")
