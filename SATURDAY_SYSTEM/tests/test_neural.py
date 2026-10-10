"""Neural curriculum — graded use cases training + proving the custom brain.

L1 single-step: every module family routes to its real command.
L2 multi-step: compound goals yield ordered executable plans.
L3 complex: conditionals (offline gates), skill replay, fairness probes.
All offline-safe (no camera/mic/screen/LLM). Live proofs run separately.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from saturday import neural as N, custom_brain as CB
from saturday.agent import AgentRunner


# -- L1: one goal → right command -----------------------------------------------
L1 = [
    ("research quantum batteries", "nsearch"),
    ("draw me a cyberpunk city", "imagine"),
    ("forge a 10 floor brick tower", "forge"),
    ("say systems online", "say"),
    ("listen for my command", "hear"),
    ("open gmail", "open"),
    ("sense the room", "sense"),
    ("start hand control", "hand"),
    ("calibrate my gaze", "gaze"),
    ("remember my keys are on the desk", "remember"),
    ("recall what you know", "recall"),
    ("take a screenshot", "see"),
    ("check system status", "status"),
    ("calc 2+2*3", "calc"),
    ("hello saturday", "cog"),
]


def test_l1_routing():
    for goal, verb in L1:
        cmds = [s["cmd"] for s in N.route_goal(goal)]
        assert any(c.split()[0] == verb for c in cmds), f"{goal} → {cmds}"


# -- L2: compound goals → ordered plans ------------------------------------------
L2 = [
    ("research fusion and announce it", ["nsearch", "say"]),
    ("open gmail and read the screen", ["open", "see"]),
]


def test_l2_multi_step():
    for goal, verbs in L2:
        cmds = [s["cmd"].split()[0] for s in N.route_goal(goal)]
        for v in verbs:
            assert v in cmds, f"{goal} → {cmds}"


# -- L3: complexity — gating table, skill replay, math truth ----------------------
def test_l3_online_gate_table():
    for verb in ("nsearch", "maps", "share", "cloudbackup"):
        assert verb in CB.ONLINE_ONLY, verb


def test_l3_skill_replay():
    CB._write_json("skills.json", {"skills": [
        {"name": "t", "trigger": "morning brief", "steps": ["briefing"],
         "uses": 5, "success_rate": 1.0, "updated": 9999999999.0}]})
    try:
        cmds = [s["cmd"] for s in N.route_goal("give me the morning brief")]
        assert cmds == ["briefing"], cmds
    finally:
        CB._write_json("skills.json", {"skills": []})


def test_l3_math_truth():
    r = N.calculate("2+2*3")
    assert r["success"] and r["numeric"] == 8.0, r
    assert N.calculate("what is 12 times 12")["numeric"] == 144.0
    assert N.calculate("calculate 15 percent of 240")["numeric"] == 36.0
    assert N.calculate("solve x squared minus 4")["exact"] == "[-2, 2]"
    assert N.calculate("solve 2x plus 3 equals 11")["exact"] == "[4]"
    assert N.calculate("integrate x squared")["exact"] == "x**3/3"
    assert not N.calculate("")[ "success"]
    assert not N.calculate("__import__('os')")["success"]  # no code exec


def test_l3_fairness_probes():
    CB.train_intent()
    rep = CB.fairness_probes()
    assert rep["passed"] == rep["total"], rep


# -- independence: CustomBrain decides with Ollama unreachable --------------------
def test_custom_brain_ollama_free():
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"  # dead port
    try:
        from saturday.agent import AgentTask
        brain = CB.CustomBrain()
        for goal in ("research fusion power", "what is 12*12", "hello saturday"):
            task = AgentTask(goal, [])
            step = brain.decide(task, {"success": True})
            checked = AgentRunner._validate_step(
                {"action": step["action"], "args": step.get("args", {})})
            assert checked.get("ok"), f"{goal} → {step}"
    finally:
        os.environ.pop("OLLAMA_HOST", None)


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("CURRICULUM GREEN")
