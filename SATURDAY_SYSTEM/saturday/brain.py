"""SATURDAY Brain — own local reasoning. Fully offline via Ollama.

OllamaBrain plugs into AgentRunner as the decider for UNSUPERVISED tasks:
it reads the goal + latest observation and emits the next action as JSON.
No cloud, no API keys, no telemetry — http://localhost:11434 only.

Capabilities:
- decide()   : text reasoning over goal/plan/observation → action dict.
- see()      : vision caption of a screenshot (moondream) so the brain
               observes the screen, not just text summaries.
- ground()   : locate a described UI element → pixel coordinates, so the
               brain can click things OCR cannot read (icons, buttons).
               Falls back to None → caller uses clicktext instead.
- available(): fast probe; anything that fails returns a safe fallback
               action ("ask" the user) instead of raising.

All HTTP uses stdlib urllib. Timeouts are generous: local CPU inference
on small models takes seconds per decision, which is fine for UI tasks.
"""

import base64
import json
import logging
import os
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from saturday.agent import Brain

logger = logging.getLogger("SATURDAY.Brain")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

ACTIONS_GUIDE = (
    "open_url(url) | open_app(app) | screenshot | read | describe | store(tags) | "
    "click(x,y) | click_text(text) | type(text) | press(key) | "
    "hotkey(k1,k2) | scroll(n) | done"
)

DECIDE_SYSTEM = (
    "You are SATURDAY, an autonomous computer operator. Given a GOAL and the "
    "LAST RESULT, output ONLY a JSON object with keys: action (one of: "
    f"{ACTIONS_GUIDE}), args (object), why (short string). "
    "Rules: prefer click_text over click with coordinates; use read after "
    "screenshot to understand screens; use describe when you need to see "
    "icons or layout OCR cannot read; call store when you have findings "
    "worth saving; call done only when the goal is achieved. "
    "Keep 'why' under 20 words."
)


class OllamaBrain(Brain):
    def __init__(self, model: str = "llama3.2", vision_model: str = "moondream",
                 host: str = OLLAMA_HOST, timeout: int = 120):
        self.model = model
        self.vision_model = vision_model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self._available: Optional[bool] = None

    # -- low-level -------------------------------------------------------
    def _post(self, path: str, payload: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.host + path, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            raise RuntimeError(f"ollama {path} failed: {e}")

    def _get(self, path: str, timeout: int = 5) -> Dict[str, Any]:
        req = urllib.request.Request(self.host + path, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())

    def available(self) -> bool:
        # Cache with 60s cooldown: stays fast on the HUD poll loop, but
        # recovers on its own if Ollama starts later (long-run stability).
        import time as _t
        now = _t.time()
        if self._available is not None and now - getattr(self, "_checked_at", 0) < 60:
            return self._available
        try:
            tags = self._get("/api/tags")
            names = [m.get("name", "") for m in tags.get("models", [])]
            self._available = any(n.startswith(self.model) or self.model in n for n in names)
            if not self._available:
                logger.warning(f"Ollama up but model '{self.model}' not pulled. Have: {names}")
        except Exception as e:
            logger.warning(f"Ollama unavailable: {e}")
            self._available = False
        self._checked_at = now
        return self._available

    def _generate(self, model: str, prompt: str, system: str = "",
                  images: Optional[List[str]] = None, json_mode: bool = True,
                  keep_alive: str = "10m", num_ctx: int = 4096) -> str:
        payload: Dict[str, Any] = {"model": model, "prompt": prompt, "stream": False,
                                   "keep_alive": keep_alive,
                                   "options": {"num_ctx": num_ctx}}
        if system:
            payload["system"] = system
        if images:
            payload["images"] = images
        if json_mode:
            payload["format"] = "json"
        out = self._post("/api/generate", payload)
        return str(out.get("response", ""))

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text)
        except Exception:
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
        return None

    # -- Brain interface ---------------------------------------------------
    def decide(self, task, observation: Dict[str, Any]) -> Dict[str, Any]:
        if not self.available():
            return {"action": "ask",
                    "prompt": "My local brain is offline (Ollama/model missing). What should I do?"}
        plan_state = f"step {task.step_idx + 1}/{max(len(task.plan), 1)}"
        obs_text = json.dumps(observation)[:1500]
        prompt = (f"GOAL: {task.goal}\nPLAN STATE: {plan_state}\n"
                  f"LAST RESULT: {obs_text}\nNext action as JSON:")
        try:
            raw = self._generate(self.model, prompt, system=DECIDE_SYSTEM)
            action = self._extract_json(raw)
            if not action or "action" not in action:
                raise ValueError(f"unparseable brain output: {raw[:200]}")
            action.setdefault("args", {})
            logger.info(f"Brain decided: {action.get('action')} ({action.get('why', '')[:80]})")
            return {"action": str(action["action"]), "args": dict(action.get("args") or {}),
                    "why": str(action.get("why", ""))[:120]}
        except Exception as e:
            logger.warning(f"Brain decide failed: {e}")
            return {"action": "ask", "prompt": f"Brain hiccup ({e}). What next? (done to finish)"}

    # -- vision --------------------------------------------------------------
    def see(self, image_path: str, question: str = "Describe this screen briefly: key windows, text, buttons.") -> Dict[str, Any]:
        try:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            # One-shot: unload vision right after so the reasoning model
            # gets full RAM on this 8GB box.
            raw = self._generate(self.vision_model, question, images=[b64],
                                 json_mode=False, keep_alive="0", num_ctx=2048)
            return {"success": True, "description": raw.strip()[:2000]}
        except Exception as e:
            logger.warning(f"Brain see failed: {e}")
            return {"success": False, "error": str(e)}

    def ground(self, target: str, image_path: str,
               image_size: Optional[tuple] = None) -> Optional[Dict[str, int]]:
        """Locate `target` on screen → {"x","y"} pixels. None if unsure."""
        try:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            q = (f"Locate the UI element: {target}. Respond with ONLY four integers "
                 f"in 0-1000 coordinates: x_min y_min x_max y_max of its bounding box.")
            raw = self._generate(self.vision_model, q, images=[b64],
                                 json_mode=False, keep_alive="0", num_ctx=2048)
            nums = [int(n) for n in re.findall(r"\d+", raw)]
            if len(nums) < 4:
                return None
            x_min, y_min, x_max, y_max = nums[:4]
            if not (0 <= x_min < x_max <= 1000 and 0 <= y_min < y_max <= 1000):
                return None
            cx, cy = (x_min + x_max) / 2 / 1000.0, (y_min + y_max) / 2 / 1000.0
            if image_size:
                return {"x": int(cx * image_size[0]), "y": int(cy * image_size[1])}
            return {"x": int(cx * 1000), "y": int(cy * 1000)}
        except Exception as e:
            logger.warning(f"Brain ground failed: {e}")
            return None
