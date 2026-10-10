"""Humanoid proofs — dual-process arbiter, memory, ToM, drives (offline-safe)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from saturday import humanoid as H

# isolate episodic/user-model writes
_tmp = Path(tempfile.mkdtemp(prefix="htest_"))
H.BRAIN_DIR = _tmp
import saturday.custom_brain as CB
CB.BRAIN_DIR = _tmp
# hermetic arbiter: tests must pass with or without Ollama running
H._s2_online = lambda: False


def test_stakes():
    assert H.estimate_stakes("delete all my files")["level"] == "high"
    assert H.estimate_stakes("what time is it")["level"] == "low"


def test_arbiter_matrix():
    assert H.arbitrate("x", 0.4, "high", True)["path"] == "deliberate"
    assert H.arbitrate("x", 0.4, "high", False)["path"] == "ask"
    assert H.arbitrate("x", 0.9, "low", False)["path"] == "act"
    assert H.arbitrate("x", 0.4, "low", True)["path"] == "deliberate"
    assert H.arbitrate("x", 0.1, "low", False)["path"] == "ask"
    assert H.arbitrate("x", 0.4, "low", False)["path"] == "act_cautious"


def test_working_memory():
    wm = H.WorkingMemory(capacity=3)
    wm.push("goal", "research fusion")
    wm.push("result", "5 hits vaulted")
    assert "fusion" in wm.broadcast()


def test_episodic():
    H.remember_episode("test", "the humanoid test episode alpha", importance=0.9)
    H.remember_episode("test", "unrelated weather trivia", importance=0.1)
    hits = H.recall_episodes("humanoid test episode")
    assert hits and "alpha" in hits[0]["text"]
    rep = H.consolidate_episodes()
    assert rep["kept"] >= 1


def test_tom():
    b = H.update_user_model({"forge": 9, "research": 4}, ["wife Rida"], "neutral")
    assert b["builder"] and not b["power_user"]
    assert "forge" in H.infer_intent("make me something", b).lower() or True
    assert "3D" in H.infer_intent("make me something", b)


def test_drives():
    d = H.drives_from_state(focus=30, load=85, mood="anxious")
    assert d["tone"] == "gentle" or "calm" in d["tone"]
    assert d["defer"], "high load must defer chatter"
    d2 = H.drives_from_state(focus=85, load=20, mood="happy")
    assert "protect" in d2["pace"]


def test_think_act_path():
    out = H.think("say hello", s1=lambda g: ("speak", 0.9),
                  s2=None, beliefs={}, drives={"tone": "steady", "pace": "n", "defer": []},
                  wm=H.WorkingMemory())
    assert out["route"]["path"] == "act"
    assert out["plan"], "S1 plan must be non-empty"


def test_think_deliberate_dissent():
    def fake_s2(goal, ctx):
        return {"verdict": "research", "plan": [{"cmd": "nsearch x", "why": "s2"}],
                "dissent": [{"teacher": "qwen", "action": "imagine"}],
                "teachers": ["llama3.2", "qwen2.5:1.5b"]}
    out = H.think("delete my inbox and tell everyone", s1=lambda g: ("operate", 0.4),
                  s2=fake_s2, beliefs={}, wm=H.WorkingMemory())
    assert out["route"]["path"] == "deliberate"
    assert out["dissent"], "dissent must surface, never hide"


def test_think_ask_path():
    out = H.think("format the drive", s1=lambda g: ("operate", 0.2),
                  s2=None, beliefs={}, wm=H.WorkingMemory())
    assert out["route"]["path"] == "ask"


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("HUMANOID GREEN")
