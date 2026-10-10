"""SATURDAY Neural — virtual neural system: many free open models, one mind.

Every model is free, open-source, and runs on THIS pc (no cloud, no keys):
  reason   : llama3.2 (Ollama) — plans, decides, explains
  vision   : moondream (Ollama) — sees screenshots, grounds UI elements
  memory   : nomic-embed-text (Ollama) + local TF-IDF — semantic recall
  ears     : faster-whisper tiny (local) — hears you
  mouth    : Piper neural TTS ryan/amy (local) — speaks back
  imagine  : sd-turbo via diffusers (local CPU) — generates images
  research : DDGS DuckDuckGo (local, no key) — searches the web
  body     : ScreenOperator/pyautogui + Blender + hands/gaze/cognition

NeuralRunner (the virtual task machine) runs any goal end-to-end:
  hear → think → act → verify → speak, logging every decision so the
  custom brain (custom_brain.py) can distill it and run Ollama-free later.

Import-light: stdlib only at import; heavy deps load lazily inside
functions so a missing model never breaks startup — probe() reports truth.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Neural")

# -- D: homes: C: is full, every byte of models/outputs lives on D: ---------
D_ROOT = Path(os.getenv("SATURDAY_D_TMP", "D:/SATURDAY_TEMP")).resolve()
D_MODELS = Path(os.getenv("SATURDAY_MODELS_DIR", r"D:\S.A.T.U.R.D.A.Y\models"))
os.environ.setdefault("HF_HOME", str(D_MODELS / "hf-hub"))
os.environ.setdefault("HF_HUB_CACHE", str(D_MODELS / "hf-hub"))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(D_MODELS / "hf-hub"))


def _d_sub(name: str) -> Path:
    p = D_ROOT / name
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


def imagine_dir() -> Path:
    return _d_sub("imagine")


def brain_log_path() -> Path:
    return _d_sub("custom_brain") / "decisions.jsonl"


# -- model roster -------------------------------------------------------------
def probe() -> Dict[str, Any]:
    """Real per-model status. Never guesses — imports + probes each one."""
    out: Dict[str, Any] = {}
    # Ollama family
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags",
                                    timeout=5) as r:
            names = [m.get("name", "") for m in
                     json.loads(r.read().decode()).get("models", [])]
        out["ollama"] = True
        out["llama3.2"] = any("llama3.2" in n for n in names)
        out["moondream"] = any("moondream" in n for n in names)
        out["nomic-embed-text"] = any("nomic-embed-text" in n for n in names)
    except Exception as e:
        out["ollama"] = False
        out["ollama_error"] = str(e)[:100]
        out["llama3.2"] = out["moondream"] = out["nomic-embed-text"] = False
    try:
        import faster_whisper  # noqa
        out["whisper"] = True
    except Exception as e:
        out["whisper"] = False
        out["whisper_error"] = str(e)[:100]
    try:
        import shutil
        vdir = D_MODELS / "piper" / "voices"
        voices = sorted(p.stem for p in vdir.glob("*.onnx")) if vdir.exists() else []
        out["piper_voices"] = voices
        out["piper"] = bool(
            (shutil.which("piper") or (D_MODELS / "piper" / "piper" / "piper.exe").exists())
            and voices)
    except Exception:
        out["piper"] = False
        out["piper_voices"] = []
    try:
        import diffusers  # noqa
        out["diffusers"] = diffusers.__version__
        w = D_MODELS / "hf-hub"
        out["sd_turbo_cached"] = any(w.rglob("*sd-turbo*")) if w.exists() else False
    except Exception:
        out["diffusers"] = None
        out["sd_turbo_cached"] = False
    try:
        import ddgs  # noqa
        out["ddgs"] = True
    except Exception:
        out["ddgs"] = False
    return out


# -- research (real web, no browser needed) ------------------------------------
def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """DDGS DuckDuckGo text search → real results. No key, no cloud account."""
    query = (query or "").strip()
    if not query:
        return {"success": False, "error": "empty query"}
    try:
        from ddgs import DDGS
        with DDGS() as ddg:
            hits = list(ddg.text(query, max_results=max(3, min(10, max_results))))
    except Exception as e:
        return {"success": False, "error": f"search failed (offline?): {e}"}
    results = [{"title": h.get("title", ""), "url": h.get("href", ""),
                "snippet": h.get("body", "")} for h in hits]
    return {"success": True, "query": query, "count": len(results),
            "results": results}


# -- imagination (real local Stable Diffusion) ---------------------------------
_IMAGINE_PIPE = None


def imagine(prompt: str, steps: int = 1, size: int = 512,
            seed: Optional[int] = None) -> Dict[str, Any]:
    """sd-turbo on CPU → real PNG. Slow on CPU (minutes) — honest timing.
    Weights download once to D: (~4GB). Uses sequential CPU offload so the
    8GB box survives."""
    prompt = (prompt or "").strip()
    if not prompt:
        return {"success": False, "error": "empty prompt"}
    steps = max(1, min(4, int(steps)))
    size = max(256, min(768, int(size)))
    global _IMAGINE_PIPE
    t0 = time.time()
    try:
        import torch
        from diffusers import AutoPipelineForText2Image
        if _IMAGINE_PIPE is None:
            print("🎨 Loading sd-turbo (first run downloads ~4GB to D:, one time)...")
            pipe = AutoPipelineForText2Image.from_pretrained(
                "stabilityai/sd-turbo", torch_dtype=torch.float32)
            try:
                pipe.enable_sequential_cpu_offload()
            except Exception:
                pass
            try:
                pipe.set_progress_bar_config(disable=True)
            except Exception:
                pass
            _IMAGINE_PIPE = pipe
            logger.info("sd-turbo loaded (CPU offload).")
        gen = torch.Generator().manual_seed(seed if seed is not None else int(time.time()) % 2**31)
        out = imagine_dir() / f"saturday_{int(time.time())}.png"
        print(f"🎨 Dreaming ({steps} step(s), {size}px — minutes on CPU, working)...")
        img = _IMAGINE_PIPE(prompt=prompt, num_inference_steps=steps,
                            guidance_scale=0.0, height=size, width=size,
                            generator=gen).images[0]
        img.save(str(out))
        secs = round(time.time() - t0, 1)
        return {"success": True, "path": str(out), "prompt": prompt,
                "steps": steps, "size": size, "seconds": secs,
                "engine": "stabilityai/sd-turbo (local CPU)"}
    except Exception as e:
        logger.warning(f"imagine failed: {e}")
        return {"success": False, "error": str(e)[:300]}


# -- mathematics (real symbolic + numeric engine) ----------------------------------
MATH_WORDS = [
    (r"(\d)\s*%", r"\1/100"),  # FIRST: 15% → 15/100 (percent beats modulo)
    (r"(.+)\bequals?\b(.+)", r"Eq(\1,\2)"),  # keep equation structure
    (r"\bsquare root of\b", "sqrt "),
    (r"\bsquared\b", "**2"),
    (r"\bcubed\b", "**3"),
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
    (r"\btimes\b|\bmultiplied by\b|\bx\b(?=\s+\d)", "*"),
    (r"\bdivided by\b|\bdivided\b|\bover\b", "/"),
    (r"\bpercent\b", "/100"),
    (r"\bof\b", "*"),
    (r"\bwhat is\b|\bcalculate\b|\bcalc\b|\bsolve\b|\bcompute\b|\bequals?\b|\bplease\b", ""),
    (r"(?<=\d)(?=[xy])", "*"),  # 2x → 2*x (implicit multiplication)
    (r"\bintegrate\b\s+(.+)", r"integrate(\1)"),  # integrate x**2 → integrate(x**2)
    (r"(?<!\w)diff\b\s+(.+)", r"diff(\1)"),
]


def words_to_math(expr: str) -> str:
    """English math → symbols: '15 percent of 240' → '15/100*240'."""
    out = f" {expr.lower()} "
    for pat, rep in MATH_WORDS:
        out = re.sub(pat, rep, out)
    return re.sub(r"\s+", " ", out).strip()


def extract_math(text: str) -> str:
    """Pull the solvable core out of a sentence: 'what is 12*12' → '12*12'."""
    t = words_to_math(text)
    m = re.search(r"([-+*/()^.%\d\w\s]+)", t)
    cand = (m.group(1).strip() if m else t).strip()
    # drop leading non-math words the regex kept (e.g. 'is')
    cand = re.sub(r"^(is|the|a|an|answer|result)\s+", "", cand)
    return cand or text


def calculate(expr: str) -> Dict[str, Any]:
    """sympy-powered math: arithmetic, algebra, calculus, matrices.
    No eval() — parsed by sympy; safe AST arithmetic if sympy missing."""
    expr = (expr or "").strip()
    if not expr:
        return {"success": False, "error": "empty expression"}
    if len(expr) > 500:
        return {"success": False, "error": "expression too long (500 chars)"}
    # whitelist gate: every bare name must be known math — nothing else parses.
    # Gate runs on the NORMALIZED text so English math words pass through.
    try:
        import ast as _ast
        _allowed_names = {"x", "y", "pi", "e", "sqrt", "sin", "cos", "tan",
                          "log", "exp", "Abs", "diff", "integrate", "simplify",
                          "factor", "solve", "Matrix", "oo", "Eq"}
        _tree = _ast.parse(words_to_math(expr).replace("^", "**"))
        for _n in _ast.walk(_tree):
            if isinstance(_n, _ast.Name) and _n.id not in _allowed_names:
                return {"success": False,
                        "error": f"unknown name {_n.id!r} — math only, no code"}
            if isinstance(_n, (_ast.Attribute, _ast.Import, _ast.ImportFrom)):
                return {"success": False, "error": "math only, no code"}
    except SyntaxError:
        pass  # sympy's friendlier parser gets the final say below
    try:
        import sympy as _sp
        # friendly names: ^ → **, plus common functions in scope
        cleaned = words_to_math(expr).replace("^", "**")
        allowed = {"x": _sp.Symbol("x"), "y": _sp.Symbol("y"),
                   "pi": _sp.pi, "e": _sp.E, "sqrt": _sp.sqrt,
                   "sin": _sp.sin, "cos": _sp.cos, "tan": _sp.tan,
                   "log": _sp.log, "exp": _sp.exp, "Abs": _sp.Abs,
                   "diff": _sp.diff, "integrate": _sp.integrate,
                   "simplify": _sp.simplify, "factor": _sp.factor,
                   "solve": _sp.solve, "Matrix": _sp.Matrix,
                   "oo": _sp.oo, "Eq": _sp.Eq}
        parsed = _sp.sympify(cleaned, locals=allowed)
        steps = []
        if re.search(r"\bsolve\b", expr, re.I) and parsed.free_symbols:
            sym = sorted(parsed.free_symbols, key=str)[0]
            sols = _sp.solve(parsed, sym)
            return {"success": True, "expression": expr,
                    "exact": str(sols), "numeric": None,
                    "steps": [f"solved for {sym}"],
                    "display": f"{sym} = {sols}", "engine": "sympy"}
        exact = str(parsed)
        try:
            numeric = float(parsed.evalf())
            try:
                same = abs(float(exact) - numeric) < 1e-9
            except Exception:
                same = False
            num_s = "" if same else f" (~{numeric:.6g})"
        except Exception:
            numeric, num_s = None, ""
        steps = []
        try:
            simp = str(_sp.simplify(parsed))
            if simp != exact:
                steps.append(f"simplified: {simp}")
        except Exception:
            pass
        return {"success": True, "expression": expr, "exact": exact,
                "numeric": numeric, "steps": steps,
                "display": f"{exact}{num_s}", "engine": "sympy"}
    except Exception as se:
        pass
    try:  # safe fallback: arithmetic only, AST-validated, no names/calls
        import ast, operator
        ops = {ast.Add: operator.add, ast.Sub: operator.sub,
               ast.Mult: operator.mul, ast.Div: operator.truediv,
               ast.Pow: operator.pow, ast.USub: operator.neg,
               ast.Mod: operator.mod}
        tree = ast.parse(expr.replace("^", "**"), mode="eval")

        def _ev(n):
            if isinstance(n, ast.Expression):
                return _ev(n.body)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                return n.value
            if isinstance(n, ast.BinOp) and type(n.op) in ops:
                return ops[type(n.op)](_ev(n.left), _ev(n.right))
            if isinstance(n, ast.UnaryOp) and type(n.op) in ops:
                return ops[type(n.op)](_ev(n.operand))
            raise ValueError("only + - * / ** % and numbers")
        val = _ev(tree)
        return {"success": True, "expression": expr, "exact": str(val),
                "numeric": float(val), "steps": [], "display": str(val),
                "engine": "safe-arithmetic"}
    except Exception as e:
        return {"success": False,
                "error": f"could not solve {expr!r}: {e}. Try: calc 2+2*3 | solve x^2-4"}


# -- distillation log (teaches the custom brain) --------------------------------
def log_decision(goal: str, observation: str, action: str,
                 args: Dict[str, Any], why: str, success: bool) -> None:
    try:
        p = brain_log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), "goal": goal[:300],
                                 "obs": observation[:300], "action": action,
                                 "args": args, "why": why[:160],
                                 "success": bool(success)}) + "\n")
    except Exception:
        pass


# -- rule planner: deterministic goal → executable commands (real router) -------
# Covers EVERY Saturday module family. Each step is a command string that
# process_command() really executes. Online-only steps are gated at run time
# (gate_online in custom_brain) — offline you get the honest alternative.
INTENT_RULES = [
    ("research", re.compile(r"\b(research|search|find out|look up|what is|who is|news)\b", re.I)),
    ("imagine", re.compile(r"\b(draw|paint|picture|image|imagine|generate an? image|meme|wallpaper)\b", re.I)),
    ("forge", re.compile(r"\b(build|model|render|forge|blender|3d|tower|house|building|skyscraper)\b", re.I)),
    ("speak", re.compile(r"\b(say|speak|announce|tell me|read out)\b", re.I)),
    ("listen", re.compile(r"\b(listen|hear|take a voice)\b", re.I)),
    ("open", re.compile(r"\b(open|launch|start|go to|browse)\b", re.I)),
    ("sense", re.compile(r"\b(sense|mood|feel|look at me|who('s| is) (here|there)|camera|heart)\b", re.I)),
    ("hand", re.compile(r"\b(hand|gesture|air control|air mouse)\b", re.I)),
    ("gaze", re.compile(r"\b(gaze|eye|stare)\b", re.I)),
    ("remember", re.compile(r"\b(remember|note this|my .* is|store this)\b", re.I)),
    ("recall", re.compile(r"\b(recall|remind me|what do you (know|remember))\b", re.I)),
    ("operate", re.compile(r"\b(click|type|press|scroll|screenshot|read the screen|hotkey)\b", re.I)),
    ("system", re.compile(r"\b(status|heal|dashboard|bot |homebot|disk|backup|share|briefing|evolve)\b", re.I)),
    ("calculate", re.compile(r"\b(calc(ulate)?|solve|integrate|what is [\d\s\+\-\*\/\^\%\.\(\)x]+|[\d\)]\s*[\+\-\*\/\^]\s*[\d\(])", re.I)),
]


def route_goal(goal: str) -> List[Dict[str, str]]:
    """Goal → ordered command plan. Deterministic, testable, executable."""
    g = (goal or "").strip()
    if not g:
        return []
    steps: List[Dict[str, str]] = []
    low = g.lower()
    # learned skills first: a mined trigger matching the goal replays it
    try:
        from saturday import custom_brain as _cb
        for s in _cb._read_json("skills.json", {"skills": []})["skills"]:
            if re.search(s.get("trigger", "^$"), g, re.I):
                for st in s.get("steps", [])[:4]:
                    steps.append({"cmd": st, "why": f"skill {s['name']}"})
                return steps
    except Exception:
        pass
    if INTENT_RULES[0][1].search(g):
        topic = re.sub(r"^(research|search( for)?|find out|look up)\s+", "", g,
                       flags=re.I).strip() or g
        steps.append({"cmd": f"nsearch {topic}", "why": "gather real web facts"})
    if INTENT_RULES[1][1].search(g):
        subj = re.sub(r"^(draw|paint|make (me )?a picture of|imagine|generate an? image of)\s+", "", g,
                      flags=re.I).strip() or g
        steps.append({"cmd": f"imagine {subj}", "why": "dream the image locally"})
    if INTENT_RULES[2][1].search(g) and "image" not in low:
        steps.append({"cmd": f"forge {g}", "why": "build it in Blender"})
    if INTENT_RULES[3][1].search(g):
        m = re.search(r"(?:say|speak|announce)\s+(.+)", g, re.I)
        steps.append({"cmd": f"say {(m.group(1) if m else g)[:200]}",
                      "why": "speak back"})
    if INTENT_RULES[4][1].search(g):
        steps.append({"cmd": "hear 5", "why": "listen to you"})
    if INTENT_RULES[5][1].search(g):
        m = re.search(r"(?:open|launch|start|go to)\s+(.+)", g, re.I)
        if m:
            steps.append({"cmd": f"open {m.group(1).strip()}", "why": "open it"})
    if INTENT_RULES[6][1].search(g):
        steps.append({"cmd": "sense", "why": "read the room"})
    if INTENT_RULES[7][1].search(g):
        steps.append({"cmd": "hand status", "why": "scan hands"})
    if INTENT_RULES[8][1].search(g) and "image" not in low and "imagine" not in low:
        steps.append({"cmd": "gaze status", "why": "check where eyes look"})
    if INTENT_RULES[9][1].search(g):
        steps.append({"cmd": f"remember {g}", "why": "vault it forever"})
    if INTENT_RULES[10][1].search(g):
        steps.append({"cmd": f"recall {re.sub(r'^(recall|remind me:?)\s*', '', g, flags=re.I)}",
                      "why": "recall from vault"})
    if INTENT_RULES[11][1].search(g):
        steps.append({"cmd": "see", "why": "look at the screen first"})
    m = re.search(r"(?:calc(?:ulate)?|solve)\s+(.+)", g, re.I)
    if m:
        steps.append({"cmd": f"calc {m.group(1).strip()}", "why": "solve it exactly"})
    elif INTENT_RULES[13][1].search(g):
        steps.append({"cmd": f"calc {g}", "why": "solve it exactly"})
    if INTENT_RULES[12][1].search(g):
        if "status" in low:
            steps.append({"cmd": "status", "why": "report health"})
        elif "heal" in low:
            steps.append({"cmd": "heal", "why": "self-repair"})
        elif "dashboard" in low:
            steps.append({"cmd": "dashboard", "why": "raise the HUD"})
        elif "briefing" in low:
            steps.append({"cmd": "briefing", "why": "speak the briefing"})
        else:
            steps.append({"cmd": "services", "why": "show all services"})
    if not steps:
        steps.append({"cmd": f"cog {g[:120]}", "why": "read mind-state first"})
    return steps


# -- the virtual task machine ----------------------------------------------------
class NeuralRunner:
    """Runs a goal across all models: plan → execute real commands → speak."""

    def __init__(self, core, max_steps: int = 8):
        self.core = core
        self.max_steps = max_steps

    def _llm_extend(self, goal: str, steps: List[Dict[str, str]]
                    ) -> List[Dict[str, str]]:
        """Ollama refines the rule plan when present; rule plan stands alone."""
        try:
            from saturday.brain import OllamaBrain
            brain = OllamaBrain(timeout=90)
            if not brain.available():
                return steps
            prompt = (f"GOAL: {goal}\nDRAFT PLAN: {json.dumps(steps)}\n"
                      "Reply ONLY JSON list of {cmd, why} using commands: "
                      "nsearch, imagine, forge, say, open, sense, gaze status, "
                      "hand status, cog, store, done. Max 6 steps.")
            raw = brain._generate(brain.model, prompt,
                                  system="You are a planner. JSON only.")
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if not m:
                return steps
            refined = json.loads(m.group(0))
            clean = [{"cmd": str(s.get("cmd", ""))[:300],
                      "why": str(s.get("why", ""))[:120]}
                     for s in refined
                     if isinstance(s, dict) and s.get("cmd")]
            return clean[:6] or steps
        except Exception as e:
            logger.debug(f"LLM planning skipped: {e}")
            return steps

    def run(self, goal: str, speak: bool = True) -> Dict[str, Any]:
        from saturday import agent as _agent
        goal = (goal or "").strip()
        if not goal:
            return {"success": False, "error": "empty goal"}
        steps = route_goal(goal)
        steps = self._llm_extend(goal, steps)
        transcript: List[Dict[str, Any]] = []
        print(f"\n🧬 Neural virtual system engaged: {goal}")
        for i, st in enumerate(steps[:self.max_steps]):
            if _agent.stop_requested():
                transcript.append({"cmd": st["cmd"], "result": "stopped"})
                break
            cmd = st["cmd"]
            # dual-mode gate: offline refuses online-only steps with alternatives
            try:
                from saturday import custom_brain as _cb
                refused = _cb.gate_online(cmd)
            except Exception:
                refused = None
            if refused:
                print(f"   [{i+1}/{len(steps)}] {cmd} → {refused[:100]}")
                transcript.append({"cmd": cmd, "result": refused})
                log_decision(goal, "", cmd.split()[0] if cmd.split() else "?",
                             {"cmd": cmd}, "offline-gate", False)
                continue
            print(f"   [{i+1}/{len(steps)}] {cmd} ({st.get('why', '')})")
            try:
                out = self.core.process_command(cmd, trusted=True)
            except Exception as e:
                out = f"❌ {e}"
            ok = not str(out).startswith("❌")
            transcript.append({"cmd": cmd, "result": str(out)[:400]})
            log_decision(goal, transcript[-2]["result"] if len(transcript) > 1 else "",
                         cmd.split()[0] if cmd.split() else "?",
                         {"cmd": cmd}, st.get("why", ""), ok)
            if cmd.strip().lower() == "done":
                break
        done = sum(1 for t in transcript if not str(t["result"]).startswith("❌"))
        summary = f"Neural run: {done}/{len(transcript)} steps worked: {goal[:100]}"
        if speak:
            try:
                self.core._speak(summary)
            except Exception:
                pass
        return {"success": done > 0, "goal": goal, "plan": steps,
                "transcript": transcript, "summary": summary}
