"""Emotion proofs — VAD polarity, opposites, empathy shape, EI probes (offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from saturday import emotion as E


def test_vad_polarity():
    assert E.analyze("I'm so happy and excited today")["vad"][0] > 0.7
    assert E.analyze("I'm sad and heartbroken")["vad"][0] < 0.3
    assert E.analyze("I'm furious at this")["vad"][1] > 0.7
    assert E.analyze("the weather is cloudy")["label"] == "neutral"


def test_negation_and_cause():
    r = E.analyze("I'm not happy about the exam")
    assert r["vad"][0] < 0.6, r
    assert E.analyze("I'm worried about my exam")["cause"] == "exam"


def test_opposites_never_mirror():
    for k, v in E.OPPOSITES.items():
        assert E.OPPOSITES[v] == k, k
    e = E.empathize("anger", 0.8, "my boss")
    assert e["tone"] == "gentle" and e["never_mirrors"] == "fear"
    assert "boss" in e["full"]


def test_ei_probes():
    rep = E.ei_probes()
    assert rep["passed"] == rep["total"], rep


def test_lexicon_honest():
    source, norms = E.load_lexicon()
    assert len(norms) > 100
    assert ("NRC" in source) or ("starter" in source), source


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("EMOTION GREEN")
